from __future__ import annotations
"""
Battery Swap Service
Enhanced battery swap execution and management
"""
from sqlmodel import Session, select
from sqlalchemy import func
from typing import List, Dict, Optional
from datetime import datetime
from app.models.rental import Rental, RentalStatus
from app.models.battery import Battery, BatteryStatus, LocationType
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
        session: Session,
        *,
        user_id: int,
        rental_id: Optional[int] = None,
        user_latitude: Optional[float] = None,
        user_longitude: Optional[float] = None,
        battery_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Get nearby station recommendations for swap.

        If rental_id/coordinates are omitted by the client, infer from the
        user's active rental and station context.
        """
        rental_stmt = select(Rental).where(
            Rental.user_id == user_id,
            Rental.status == RentalStatus.ACTIVE,
        )
        if rental_id is not None:
            rental_stmt = rental_stmt.where(Rental.id == rental_id)

        rental = session.exec(
            rental_stmt.order_by(Rental.start_time.desc())
        ).first()
        if not rental:
            return []

        battery = session.get(Battery, rental.battery_id)
        if not battery:
            return []

        if user_latitude is None or user_longitude is None:
            station_id_fallback = battery.station_id or rental.start_station_id
            fallback_station = session.get(Station, station_id_fallback) if station_id_fallback else None
            if fallback_station is not None:
                user_latitude = fallback_station.latitude
                user_longitude = fallback_station.longitude

        if user_latitude is None or user_longitude is None:
            return []

        normalized_type = (battery_type or "").strip().lower()

        stations = session.exec(
            select(Station)
            .where(func.replace(func.replace(func.lower(Station.status), "-", "_"), " ", "_") == "active")
            .where(Station.is_deleted == False)
        ).all()

        suggestions = []

        for station in stations:
            distance = GPSTrackingService.calculate_distance(
                user_latitude,
                user_longitude,
                station.latitude,
                station.longitude,
            )

            if distance > 20:
                continue

            available_stmt = (
                select(Battery)
                .where(Battery.location_id == station.id)
                .where(Battery.location_type == LocationType.STATION)
                .where(Battery.status == BatteryStatus.AVAILABLE)
                .where(Battery.current_charge >= 80)
                .where(Battery.health_percentage >= 85)
            )
            if normalized_type:
                available_stmt = available_stmt.where(
                    func.lower(func.coalesce(Battery.battery_type, "")) == normalized_type
                )

            available_batteries = session.exec(available_stmt).all()

            if not available_batteries:
                continue

            travel_time_minutes = max(1, int(round((distance / 30) * 60)))
            best_battery = max(available_batteries, key=lambda item: float(item.current_charge or 0.0))
            supported_types = sorted({
                (item.battery_type or "").strip()
                for item in available_batteries
                if (item.battery_type or "").strip()
            })

            suggestions.append({
                'station_id': station.id,
                'station_name': station.name,
                'address': station.address,
                'distance_km': round(distance, 2),
                'travel_time_minutes': travel_time_minutes,
                'available_batteries': len(available_batteries),
                'best_battery_soc': float(best_battery.current_charge or 0.0),
                'recommended_battery_id': best_battery.id,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'operating_hours': station.operating_hours or ("24/7" if station.is_24x7 else "N/A"),
                'supported_battery_types': supported_types,
                'total_capacity': station.total_slots or station.max_capacity or 0,
            })

        suggestions.sort(
            key=lambda item: (
                item['distance_km'],
                -item['available_batteries'],
                -item['best_battery_soc'],
            )
        )
        bounded_limit = max(1, min(int(limit), 20))
        return suggestions[:bounded_limit]
    
    @staticmethod
    def execute_swap(
        rental_id: int,
        new_battery_id: int,
        station_id: int,
        session: Session,
        *,
        auto_commit: bool = True,
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
            if not rental or rental.status != RentalStatus.ACTIVE:
                raise ValueError("Invalid rental")
            
            # Get old battery
            old_battery = session.exec(select(Battery).where(Battery.id == rental.battery_id).with_for_update()).first()
            if not old_battery:
                raise ValueError("Old battery not found")
            
            # Get new battery
            new_battery = session.exec(select(Battery).where(Battery.id == new_battery_id).with_for_update()).first()
            if not new_battery or new_battery.status != BatteryStatus.AVAILABLE:
                raise ValueError("New battery not available")
            
            # Verify new battery is at the station
            if new_battery.location_id != station_id or new_battery.location_type != LocationType.STATION:
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
            
            if auto_commit:
                SwapService._safe_commit(session, context="execute_swap")
            else:
                session.flush()
            
            logger.info("swap.completed", rental_id=rental_id, old_battery=old_battery.serial_number, new_battery=new_battery.serial_number)
            return True
            
        except Exception as e:
            if auto_commit:
                session.rollback()
            logger.error("swap.failed", rental_id=rental_id, error=str(e))
            if auto_commit:
                return False
            raise
    
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
