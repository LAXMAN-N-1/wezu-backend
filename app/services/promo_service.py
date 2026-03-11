from typing import List
from sqlmodel import Session, select
from app.models.promo_code import PromoCode
from datetime import datetime
from fastapi import HTTPException
from typing import List

class PromoService:
    @staticmethod
    def validate_promo(db: Session, code: str, order_amount: float) -> dict:
        promo = db.exec(select(PromoCode).where(PromoCode.code == code)).first()
        
        if not promo:
            raise HTTPException(status_code=404, detail="Invalid promo code")
            
        if not promo.is_active:
            raise HTTPException(status_code=400, detail="Promo code is inactive")
            
        # Check validity dates
        now = datetime.utcnow()
        if promo.valid_until and now > promo.valid_until:
            raise HTTPException(status_code=400, detail="Promo code expired")
        if now < promo.valid_from:
             raise HTTPException(status_code=400, detail="Promo code not yet valid")
    
        # Check limits
        if promo.usage_limit > 0 and promo.usage_count >= promo.usage_limit:
            raise HTTPException(status_code=400, detail="Promo code usage limit reached")
            
        if order_amount < promo.min_order_amount:
            raise HTTPException(status_code=400, detail=f"Minimum order amount is {promo.min_order_amount}")
    
        # Calculate discount
        discount = 0.0
        if promo.discount_percentage > 0:
            discount = (promo.discount_percentage / 100) * order_amount
            if promo.max_discount_amount:
                discount = min(discount, promo.max_discount_amount)
        else:
             discount = promo.discount_amount
        
        final_amount = max(0, order_amount - discount)
        
        return {
            "code": promo.code,
            "discount": discount,
            "final_amount": final_amount,
            "promo_id": promo.id
        }
    
    @staticmethod
    def apply_promo(db: Session, promo_id: int):
        """Apply validated coupon to an active order"""
        promo = db.get(PromoCode, promo_id)
        if promo:
            promo.usage_count += 1
            db.add(promo)
            db.commit()
            return True
        return False
    
    @staticmethod
    def create_promo(db: Session, promo_in: PromoCode) -> PromoCode:
        """Admin: create a coupon/promo code"""
        db.add(promo_in)
        db.commit()
        db.refresh(promo_in)
        return promo_in
    
    @staticmethod
    def update_promo(db: Session, promo_id: int, update_data: dict) -> PromoCode:
        """Admin: update or deactivate a coupon"""
        promo = db.get(PromoCode, promo_id)
        if not promo:
            raise HTTPException(status_code=404, detail="Promo not found")
        
        for field, value in update_data.items():
            setattr(promo, field, value)
            
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo
    
    @staticmethod
    def list_all_promos(db: Session) -> List[PromoCode]:
        """Admin: list all coupons with usage stats"""
        return db.exec(select(PromoCode)).all()
