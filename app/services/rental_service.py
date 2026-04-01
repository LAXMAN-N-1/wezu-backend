from sqlmodel import Session, select
from app.models.rental import Rental
from app.models.rental_event import RentalEvent
from app.models.battery import Battery
from app.models.user import User
from app.schemas.rental import RentalCreate
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC, timedelta
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
            from app.models.promo_code import PromoCode
            promo = db.exec(select(PromoCode).where(PromoCode.code == promo_code, PromoCode.is_active == True)).first()
            
            if not promo:
                raise HTTPException(status_code=400, detail="Invalid or inactive promo code")
                
            now = datetime.now(UTC)
            # Ensure timezone awareness matches
            valid_until = promo.valid_until.replace(tzinfo=UTC) if promo.valid_until and promo.valid_until.tzinfo is None else promo.valid_until
            
            if valid_until and valid_until < now:
                raise HTTPException(status_code=400, detail="Promo code has expired")
                
            if promo.usage_limit > 0 and promo.usage_count >= promo.usage_limit:
                raise HTTPException(status_code=400, detail="Promo code usage limit reached")
                
            if duration_days < promo.min_rental_days:
                raise HTTPException(status_code=400, detail=f"Promo code requires minimum {promo.min_rental_days} rental days")
                
            if total_rent < promo.min_order_amount:
                raise HTTPException(status_code=400, detail=f"Promo code requires minimum order amount of {promo.min_order_amount}")
                
            if promo.discount_percentage > 0:
                calc_discount = total_rent * (promo.discount_percentage / 100.0)
                if promo.max_discount_amount:
                    calc_discount = min(calc_discount, promo.max_discount_amount)
                discount = calc_discount
            elif promo.discount_amount > 0:
                discount = promo.discount_amount
                
            discount = min(discount, total_rent)
            promo_id = promo.id
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
            start_station_id=rental_in.start_station_id, # Corrected field name
            start_time=datetime.now(UTC),
            expected_end_time=datetime.now(UTC) + timedelta(days=rental_in.duration_days),
            status="pending_payment",
            # Metrics
            total_amount=price_details["total_payable"], # Corrected field name
            security_deposit=price_details["deposit"],
        )
        db.add(rental)
        
        # Reserve battery
        battery.status = "reserved"
        db.add(battery)
        
        db.commit()
        db.refresh(rental)
        return rental

    @staticmethod
    def confirm_rental(db: Session, user_id: int, rental_id: int, payment_ref: str) -> Rental:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != "pending_payment":
            raise HTTPException(status_code=400, detail="Invalid rental state")
            
        if rental.user_id != user_id:
             raise HTTPException(status_code=403, detail="Not authorized")

        # 1. Deduct from Wallet
        from app.services.wallet_service import WalletService
        from app.services.commission_service import CommissionService
        try:
            txn = WalletService.deduct_balance(
                db, 
                user_id, 
                rental.total_amount, 
                f"Rental Payment for Battery {rental.battery_id}"
            )
            # 1.1 Calculate and Log Commissions
            CommissionService.calculate_and_log(db, txn)
        except HTTPException as e:
            # Re-raise insufficient funds or other wallet errors
            raise e
            
        # 2. Update Rental Status
        rental.status = "active"
        rental.payment_transaction_id = payment_ref
        rental.terms_accepted_at = datetime.now(UTC)
        
        # 3. Update Battery status
        battery = db.get(Battery, rental.battery_id)
        if battery:
            battery.status = "rented"
            battery.current_user_id = user_id
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
             
        from app.services.late_fee_service import LateFeeService
        fee_details = LateFeeService.calculate_late_fee(rental_id, db)
        
        if fee_details.get("late_fee", 0) > 0:
            LateFeeService.apply_late_fee(rental_id, db)
            
        rental.status = "completed"
        rental.end_station_id = station_id # Corrected field name
        rental.end_time = datetime.now(UTC) # Corrected field name
        
        battery = db.get(Battery, rental.battery_id)
        if battery:
            battery.status = "available"
            db.add(battery)
         
        db.add(rental)
        
        # 1. Award loyalty points on completion
        from app.services.membership_service import MembershipService
        MembershipService.earn_points(db, rental.user_id, rental.total_amount)
        
        event = RentalEvent(
            rental_id=rental.id,
            event_type="stop",
            station_id=station_id,
            battery_id=rental.battery_id,
            description=f"Rental completed. Points awarded."
        )
        db.add(event)
        
        db.commit()
        db.refresh(rental)
        return rental

    @staticmethod
    def cancel_rental(db: Session, rental_id: int, user_id: int) -> bool:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != "pending_payment":
            return False
            
        if rental.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        battery = db.get(Battery, rental.battery_id)
        if battery:
            battery.status = "available"
            db.add(battery)
            
        rental.status = "cancelled"
        db.add(rental)
        db.commit()
        return True

    @staticmethod
    def initiate_return(db: Session, rental_id: int, station_id: int) -> Rental:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status != "active":
             raise HTTPException(status_code=400, detail="Rental is not in a returnable state")
             
        rental.status = "returning"
        rental.end_station_id = station_id
        db.add(rental)
        db.commit()
        db.refresh(rental)
        return rental

    @staticmethod
    def complete_rental(db: Session, rental_id: int) -> Rental:
        rental = db.get(Rental, rental_id)
        if not rental or rental.status not in ["active", "returning"]:
             raise HTTPException(status_code=400, detail="Invalid rental state for completion")
             
        # Reuse existing return logic but make it definitive
        return RentalService.return_battery(db, rental_id, rental.end_station_id or rental.start_station_id)

    @staticmethod
    def get_analytics(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        stmt = select(Rental).where(Rental.start_time >= start_date, Rental.start_time <= end_date)
        rentals = db.exec(stmt).all()
        
        total = len(rentals)
        active = len([r for r in rentals if r.status == "active"])
        completed = len([r for r in rentals if r.status == "completed"])
        
        total_revenue = sum(r.total_amount for r in rentals)
        
        completed_durations = [(r.end_time - r.start_time).total_seconds() for r in rentals if r.end_time]
        avg_dur = (sum(completed_durations) / len(completed_durations)) / 3600 if completed_durations else 0
        
        # Group by station
        station_counts = {}
        for r in rentals:
            s_id = r.start_station_id
            station_counts[s_id] = station_counts.get(s_id, 0) + 1
            
        return {
            "total_rentals": total,
            "active_rentals": active,
            "completed_rentals": completed,
            "avg_duration_hours": round(avg_dur, 2),
            "total_revenue": round(total_revenue, 2),
            "rentals_by_station": [{"station_id": sid, "count": count} for sid, count in station_counts.items()]
        }
