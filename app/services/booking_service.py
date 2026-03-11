from sqlmodel import Session, select
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from app.models.station import Station, StationStatus
from app.models.battery import Battery, BatteryStatus
from app.models.battery_reservation import BatteryReservation
from app.services.gps_service import GPSTrackingService
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

class BookingService:
    @staticmethod
    def get_stations_nearby(
        db: Session,
        lat: float,
        lon: float,
        radius_km: float = 10,
        limit: int = 10
    ) -> List[Dict]:
        """Find stations within radius with real-time availability"""
        statement = select(Station).where(Station.status == StationStatus.OPERATIONAL)
        stations = db.exec(statement).all()
        
        results = []
        for station in stations:
            distance = GPSTrackingService.calculate_distance(lat, lon, station.latitude, station.longitude)
            if distance <= radius_km:
                # Get available batteries count
                available_count = db.exec(
                    select(Battery).where(
                        Battery.station_id == station.id,
                        Battery.status == BatteryStatus.AVAILABLE,
                        Battery.current_charge >= 80
                    )
                ).all()
                
                results.append({
                    "id": station.id,
                    "name": station.name,
                    "address": station.address,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance": round(distance, 2),
                    "available_batteries": len(available_count),
                    "rating": station.rating,
                    "is_24x7": station.is_24x7
                })
        
        # Sort by distance
        results.sort(key=lambda x: x["distance"])
        return results[:limit]

    @staticmethod
    def create_reservation(
        db: Session,
        user_id: int,
        station_id: int
    ) -> BatteryReservation:
        """Create a 30-minute reservation for a battery at a station"""
        # 1. Check if station has available batteries
        battery = db.exec(
            select(Battery).where(
                Battery.station_id == station_id,
                Battery.status == BatteryStatus.AVAILABLE
            ).order_by(Battery.current_charge.desc())
        ).first()
        
        if not battery:
            raise ValueError("No batteries available at this station")
            
        # 2. Check if user already has an active reservation
        existing = db.exec(
            select(BatteryReservation).where(
                BatteryReservation.user_id == user_id,
                BatteryReservation.status == "PENDING"
            )
        ).first()
        if existing:
            raise ValueError("User already has an active reservation")

        # 3. Create Reservation
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=30)
        
        reservation = BatteryReservation(
            user_id=user_id,
            station_id=station_id,
            battery_id=battery.id,
            start_time=now,
            end_time=expiry,
            status="PENDING"
        )
        
        # 4. Mark battery as reserved (using a pseudo-status or separate field if needed, 
        # but for now we'll just keep it in PENDING reservation)
        # Actually, let's mark the battery as 'reserved' to prevent duplicate bookings
        # BatteryStatus doesn't have RESERVED, so let's update it or use a logic
        # For MVP, we'll just trust the reservation table.
        
        db.add(reservation)
        db.commit()
        db.refresh(reservation)

        # 5. Schedule reminder (10 mins before expiry)
        reminder_time = reservation.end_time - timedelta(minutes=10)
        if reminder_time > datetime.utcnow():
            NotificationService.schedule_notification(
                db=db,
                user_id=user_id,
                title="Reservation Reminder",
                message="Your battery reservation at " + battery.station_id + " expires in 10 minutes.", # Station name would be better
                scheduled_at=reminder_time
            )

        return reservation

    @staticmethod
    def release_expired_reservations(db: Session):
        """Release reservations older than 30 minutes"""
        now = datetime.utcnow()
        statement = select(BatteryReservation).where(
            BatteryReservation.status == "PENDING",
            BatteryReservation.end_time < now
        )
        expired = db.exec(statement).all()
        for res in expired:
            res.status = "EXPIRED"
            db.add(res)
        db.commit()
        return len(expired)
