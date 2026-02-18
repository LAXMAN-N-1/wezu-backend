from sqlmodel import Session, select
from app.models.rental import Rental
from app.models.rental_event import RentalEvent
from app.models.battery import Battery
from app.models.user import User
from app.schemas.rental import RentalCreate
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.services.security_service import SecurityService

class RentalService:
    @staticmethod
    def calculate_price(db: Session, battery_id: int, duration_days: int, promo_code: Optional[str] = None):
        battery = db.get(Battery, battery_id)
        if not battery:
            raise HTTPException(status_code=404, detail="Battery not found")
            
        daily_rate = battery.rental_price_per_day
        deposit = battery.damage_deposit_amount
        total_rent = daily_rate * duration_days
        discount = 0.0
        promo_id = None
        
        if promo_code:
            # TODO: Implement PromoCode validation logic
            pass
            
        return {
            "daily_rate": daily_rate,
            "duration_days": duration_days,
            "rental_cost": total_rent,
            "discount": discount,
            "deposit": deposit,
            "total_payable": total_rent - discount + deposit,
            "promo_code_id": promo_id
        }

    @staticmethod
    def initiate_rental(db: Session, user_id: int, rental_in: RentalCreate) -> Rental:
        # 1. Enforce single active rental constraint
        active_rental = db.exec(
            select(Rental).where(
                Rental.user_id == user_id, 
                Rental.status.in_(["active", "pending_payment"])
            )
        ).first()
        if active_rental:
            raise HTTPException(
                status_code=400, 
                detail="User already has an active rental or pending payment"
            )

        # 2. Verify battery availability
        battery = db.get(Battery, rental_in.battery_id)
        if not battery or battery.status not in ["ready", "available"]:
             raise HTTPException(status_code=400, detail="Battery is not available for rental")
        
        # 3. Calculate final price
        price_details = RentalService.calculate_price(db, rental_in.battery_id, rental_in.duration_days, rental_in.promo_code)
        
        # 4. Create Rental (PENDING_PAYMENT)
        rental = Rental(
            user_id=user_id,
            battery_id=rental_in.battery_id,
            pickup_station_id=rental_in.pickup_station_id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(days=rental_in.duration_days),
            status="pending_payment",
            rental_duration_days=rental_in.duration_days,
            daily_rate=price_details["daily_rate"],
            damage_deposit=price_details["deposit"],
            discount_amount=price_details["discount"],
            total_price=price_details["total_payable"],
            promo_code_id=price_details["promo_code_id"]
        )
        db.add(rental)
        
        # Reserve battery
        battery.status = "reserved"
        db.add(battery)
        
        db.commit()
        db.refresh(rental)
        return rental

    @staticmethod
    def confirm_rental(db: Session, rental_id: int, payment_ref: str) -> Rental:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != "pending_payment":
            raise HTTPException(status_code=400, detail="Invalid rental state")
            
        rental.status = "active"
        rental.payment_transaction_id = payment_ref
        rental.terms_accepted_at = datetime.utcnow()
        
        # Update Battery status
        battery = db.get(Battery, rental.battery_id)
        if battery:
            battery.status = "rented"
            db.add(battery)
        
        db.add(rental)
        db.commit()
        db.refresh(rental)
        return rental

    @staticmethod
    def get_active_rentals(db: Session, user_id: int) -> List[Rental]:
        from sqlalchemy.orm import selectinload
        return db.exec(
            select(Rental)
            .where(Rental.user_id == user_id, Rental.status == "active")
            .options(selectinload(Rental.battery))
        ).all()

    @staticmethod
    def get_current_rental(db: Session, user_id: int) -> Optional[Rental]:
        from sqlalchemy.orm import selectinload
        return db.exec(
            select(Rental)
            .where(Rental.user_id == user_id, Rental.status.in_(["active", "pending_payment"]))
            .options(selectinload(Rental.battery))
        ).first()

    @staticmethod
    def get_history(db: Session, user_id: int) -> List[Rental]:
        from sqlalchemy.orm import selectinload
        return db.exec(
            select(Rental)
            .where(Rental.user_id == user_id)
            .options(selectinload(Rental.battery))
            .order_by(Rental.start_time.desc())
        ).all()

    @staticmethod
    def return_battery(db: Session, rental_id: int, station_id: int) -> Rental:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != "active":
             raise HTTPException(status_code=400, detail="Invalid rental")
             
        rental.status = "completed"
        rental.drop_station_id = station_id
        
        battery = db.get(Battery, rental.battery_id)
        if battery:
            battery.status = "available"
            db.add(battery)
         
        db.add(rental)
        
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
