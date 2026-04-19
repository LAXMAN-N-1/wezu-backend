from __future__ import annotations
"""
Battery Swap Service
Enhanced battery swap execution and management
"""
from sqlmodel import Session, select
from sqlalchemy import func
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.models.rental import Rental
from app.models.battery import Battery
from app.models.station import Station
from app.services.gps_service import GPSTrackingService
from app.services.battery_consistency import apply_battery_transition
from app.core.logging import get_logger

logger = get_logger("wezu_swaps")

class SwapService:
    """Battery swap management"""

    @staticmethod
    def _safe_commit(session: Session, *, context: str = "swap_service") -> None:
        """Commit with rollback-on-failure and structured logging."""
        try:
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("db.commit_failed", context=context)
            raise

    @staticmethod
    def get_swap_suggestions(
        rental_id: int,
        user_latitude: float,
        user_longitude: float,
        session: Session
    ) -> List[Dict]:
        """
        Get smart swap station suggestions
        
        Args:
            rental_id: Current rental ID
            user_latitude: User's current latitude
            user_longitude: User's current longitude
            session: Database session
            
        Returns:
            List of suggested stations with details
        """
        # Get rental details
        rental = session.get(Rental, rental_id)
        if not rental:
            return []
        
        # Get current battery
        battery = session.get(Battery, rental.battery_id)
        if not battery:
            return []
        
        # Find nearby stations with available batteries
        stations = session.exec(
            select(Station)
            .where(func.replace(func.replace(func.lower(Station.status), "-", "_"), " ", "_") == "active")
            .where(Station.is_deleted == False)
        ).all()
        
        suggestions = []
        
        for station in stations:
            # Calculate distance
            distance = GPSTrackingService.calculate_distance(
                user_latitude, user_longitude,
                station.latitude, station.longitude
            )
            
            # Only consider stations within 10km
            if distance > 10:
                continue
            
            # Count available batteries at station
            available_batteries = session.exec(
                select(Battery)
                .where(Battery.location_id == station.id)
                .where(Battery.location_type == "station")
                .where(Battery.status == "available")
                .where(Battery.current_charge >= 80)  # At least 80% charged
                .where(Battery.health_percentage >= 85)  # Good health
            ).all()
            
            if not available_batteries:
                continue
            
            # Calculate estimated travel time (assume 30 km/h average)
            travel_time_minutes = int((distance / 30) * 60)
            
            suggestions.append({
                'station_id': station.id,
                'station_name': station.name,
                'address': station.address,
                'distance_km': round(distance, 2),
                'travel_time_minutes': travel_time_minutes,
                'available_batteries': len(available_batteries),
                'best_battery_soc': max(b.current_charge for b in available_batteries),
                'latitude': station.latitude,
                'longitude': station.longitude,
                'operating_hours': station.operating_hours or ("24/7" if station.is_24x7 else "N/A")
            })
        
        # Sort by distance
        suggestions.sort(key=lambda x: x['distance_km'])
        
        return suggestions[:5]  # Return top 5
    
    @staticmethod
    def execute_swap(
        rental_id: int,
        new_battery_id: int,
        station_id: int,
        session: Session
    ) -> bool:
        """
        Execute battery swap
        
        Args:
            rental_id: Current rental ID
            new_battery_id: New battery ID
            station_id: Station where swap happens
            session: Database session
            
        Returns:
            True if successful
        """
        try:
            # Get rental
            rental = session.exec(select(Rental).where(Rental.id == rental_id).with_for_update()).first()
            if not rental or rental.status != "active":
                raise ValueError("Invalid rental")
            
            # Get old battery
            old_battery = session.exec(select(Battery).where(Battery.id == rental.battery_id).with_for_update()).first()
            if not old_battery:
                raise ValueError("Old battery not found")
            
            # Get new battery
            new_battery = session.exec(select(Battery).where(Battery.id == new_battery_id).with_for_update()).first()
            if not new_battery or new_battery.status != "available":
                raise ValueError("New battery not available")
            
            # Verify new battery is at the station
            if new_battery.location_id != station_id or new_battery.location_type != "station":
                raise ValueError("Battery not at specified station")
            
            # Return old battery to station
            apply_battery_transition(
                session,
                battery=old_battery,
                to_status="available",
                to_location_type="station",
                to_location_id=station_id,
                event_type="swap_returned",
                event_description=f"Swap return for rental #{rental_id} at station #{station_id}",
            )
            
            # Assign new battery to rental/customer possession.
            apply_battery_transition(
                session,
                battery=new_battery,
                to_status="deployed",
                to_location_type="customer",
                to_location_id=None,
                event_type="swap_dispensed",
                event_description=f"Swap dispense for rental #{rental_id} at station #{station_id}",
            )
            
            # Update rental
            rental.battery_id = new_battery_id
            session.add(rental)
            
            # Log swap event
            from app.models.rental_event import RentalEvent
            swap_event = RentalEvent(
                rental_id=rental_id,
                event_type="swap_complete",
                description=f"Swapped battery from {old_battery.serial_number} to {new_battery.serial_number} at station {station_id}",
                station_id=station_id,
                battery_id=new_battery_id,
                created_at=datetime.utcnow(),
            )
            session.add(swap_event)
            
            SwapService._safe_commit(session, context="execute_swap")
            
            logger.info("swap.completed", rental_id=rental_id, old_battery=old_battery.serial_number, new_battery=new_battery.serial_number)
            return True
            
        except Exception as e:
            session.rollback()
            logger.error("swap.failed", rental_id=rental_id, error=str(e))
            return False
    
    @staticmethod
    def calculate_swap_fee(rental_id: int, session: Session) -> float:
        """
        Calculate swap fee (currently free for customers)
        
        Args:
            rental_id: Rental ID
            session: Database session
            
        Returns:
            Swap fee amount
        """
        # Currently free as per requirements
        return 0.0
    
    @staticmethod
    def get_swap_history(rental_id: int, session: Session) -> List[Dict]:
        """Get swap history for rental"""
        from app.models.rental_event import RentalEvent
        
        swaps = session.exec(
            select(RentalEvent)
            .where(RentalEvent.rental_id == rental_id)
            .where(RentalEvent.event_type == "swap_complete")
            .order_by(RentalEvent.created_at.desc())
        ).all()
        
        return [
            {
                'timestamp': swap.created_at.isoformat(),
                'description': swap.description
            }
            for swap in swaps
        ]
