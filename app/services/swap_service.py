"""
Battery Swap Service
Enhanced battery swap execution and management
"""
from sqlmodel import Session, select
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.models.rental import Rental
from app.models.battery import Battery
from app.models.station import Station
from app.services.gps_service import GPSTrackingService
import logging

logger = logging.getLogger(__name__)

class SwapService:
    """Battery swap management"""
    
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
            select(Station).where(Station.is_active == True)
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
                .where(Battery.station_id == station.id)
                .where(Battery.status == "available")
                .where(Battery.current_soc >= 80)  # At least 80% charged
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
                'best_battery_soc': max(b.current_soc for b in available_batteries),
                'latitude': station.latitude,
                'longitude': station.longitude,
                'operating_hours': f"{station.opening_time} - {station.closing_time}" if station.opening_time else "24/7"
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
            rental = session.get(Rental, rental_id)
            if not rental or rental.status != "active":
                raise ValueError("Invalid rental")
            
            # Get old battery
            old_battery = session.get(Battery, rental.battery_id)
            if not old_battery:
                raise ValueError("Old battery not found")
            
            # Get new battery
            new_battery = session.get(Battery, new_battery_id)
            if not new_battery or new_battery.status != "available":
                raise ValueError("New battery not available")
            
            # Verify new battery is at the station
            if new_battery.station_id != station_id:
                raise ValueError("Battery not at specified station")
            
            # Return old battery to station
            old_battery.status = "available"
            old_battery.station_id = station_id
            session.add(old_battery)
            
            # Assign new battery to rental
            new_battery.status = "rented"
            new_battery.station_id = None
            session.add(new_battery)
            
            # Update rental
            rental.battery_id = new_battery_id
            session.add(rental)
            
            # Log swap event
            from app.models.rental import RentalHistory
            swap_event = RentalHistory(
                rental_id=rental_id,
                event_type="BATTERY_SWAP",
                description=f"Swapped battery from {old_battery.serial_number} to {new_battery.serial_number} at station {station_id}",
                timestamp=datetime.utcnow()
            )
            session.add(swap_event)
            
            session.commit()
            
            logger.info(f"Battery swap completed for rental {rental_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to execute swap: {str(e)}")
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
        from app.models.rental import RentalHistory
        
        swaps = session.exec(
            select(RentalHistory)
            .where(RentalHistory.rental_id == rental_id)
            .where(RentalHistory.event_type == "BATTERY_SWAP")
            .order_by(RentalHistory.timestamp.desc())
        ).all()
        
        return [
            {
                'timestamp': swap.timestamp.isoformat(),
                'description': swap.description
            }
            for swap in swaps
        ]
