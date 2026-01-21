from sqlmodel import Session, select
from app.models.promo_code import PromoCode
from datetime import datetime
from fastapi import HTTPException

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
        promo = db.get(PromoCode, promo_id)
        if promo:
            promo.usage_count += 1
            db.add(promo)
            db.commit()
