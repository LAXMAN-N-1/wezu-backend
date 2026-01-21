from sqlmodel import Session, select
from app.models.rental import Rental
from app.models.rental_event import RentalEvent
from app.models.battery import Battery
from app.models.user import User
from app.schemas.rental import RentalCreate
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException

class RentalService:
    @staticmethod
    def create_rental(db: Session, user_id: int, rental_in: RentalCreate) -> Rental:
        # 1. Verify battery availability
        battery = db.get(Battery, rental_in.battery_id)
        if not battery or battery.status != "available":
            raise HTTPException(status_code=400, detail="Battery not available")
            
        # 2. Create Rental
        rental = Rental(
            user_id=user_id,
            battery_id=rental_in.battery_id,
            pickup_station_id=rental_in.pickup_station_id,
            start_time=datetime.utcnow(),
            # Initial end time based on planned duration, but rental is open-ended usually?
            # Or fixed duration. Prompt says "Confirm rental duration (1-30 days)".
            end_time=datetime.utcnow() + timedelta(days=rental_in.duration_days),
            status="active"
        )
        db.add(rental)
        
        # 3. Update Battery Status
        battery.status = "rented"
        db.add(battery)
        
        # 4. Create Event
        event = RentalEvent(
            rental=rental,
            event_type="start",
            station_id=rental_in.pickup_station_id,
            battery_id=rental_in.battery_id,
            description=f"Rental started for {rental_in.duration_days} days"
        )
        db.add(event)
        
        db.commit()
        db.refresh(rental)
        return rental

    @staticmethod
    def get_active_rentals(db: Session, user_id: int) -> List[Rental]:
        return db.exec(select(Rental).where(Rental.user_id == user_id, Rental.status == "active")).all()

    @staticmethod
    def get_history(db: Session, user_id: int) -> List[Rental]:
        return db.exec(select(Rental).where(Rental.user_id == user_id).order_by(Rental.start_time.desc())).all()

    @staticmethod
    def return_battery(db: Session, rental_id: int, station_id: int) -> Rental:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != "active":
             raise HTTPException(status_code=400, detail="Invalid rental")
             
        rental.status = "completed"
        rental.drop_station_id = station_id
        # Calculate final price if needed (or late fees)
        
        battery = db.get(Battery, rental.battery_id)
        battery.status = "available"
        # Update battery location to this station? Station needs slots update.
        # Assuming IoT updates station slot.
         
        db.add(rental)
        db.add(battery)
        
        event = RentalEvent(
            rental_id=rental.id,
            event_type="stop",
            station_id=station_id,
            battery_id=rental.battery_id,
            description="Rental completed"
        )
        db.add(event)
        
        db.commit()
        db.refresh(rental)
        return rental
