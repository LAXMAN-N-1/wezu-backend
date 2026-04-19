from __future__ import annotations
from sqlmodel import Session, select
from app.models.referral import Referral
from app.models.user import User
from app.utils.helpers import generate_random_string
from fastapi import HTTPException

class ReferralService:
    @staticmethod
    def generate_referral_code(db: Session, user_id: int) -> Referral:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Check existing
        existing = db.exec(select(Referral).where(Referral.referrer_id == user_id, Referral.status == "pending")).first()
        if existing:
            return existing

        code = generate_random_string(8).upper()
        # Verify uniqueness loop could be added here
        
        referral = Referral(
            referrer_id=user_id,
            referral_code=code,
            status="pending"
        )
        db.add(referral)
        db.commit()
        db.refresh(referral)
        return referral

    @staticmethod
    def claim_referral(db: Session, code: str, new_user_id: int):
        referral = db.exec(select(Referral).where(Referral.referral_code == code, Referral.status == "pending")).first()
        
        if not referral:
             raise HTTPException(status_code=404, detail="Invalid referral code")
             
        if referral.referrer_id == new_user_id:
             raise HTTPException(status_code=400, detail="Cannot refer yourself")

        referral.referred_user_id = new_user_id
        referral.status = "completed"
        # Add reward logic here (e.g., wallet credit)
        
        db.add(referral)
        db.commit()
        return {"status": "success", "message": "Referral claimed"}
