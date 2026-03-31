from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select, func
from app.models.otp import OTP
from app.models.fraud import Blacklist
from typing import Optional
import logging

logger = logging.getLogger("wezu_fraud")

class FraudService:
    @staticmethod
    def check_velocity(db: Session, target: str, action_type: str, limit: int = 3, window_minutes: int = 10) -> bool:
        """
        Check if an action has been performed too many times within a window.
        Returns True if action is allowed, False if velocity limit exceeded.
        """
        if action_type == "otp":
            window_start = datetime.now(UTC) - timedelta(minutes=window_minutes)
            statement = select(func.count(OTP.id)).where(
                OTP.target == target,
                OTP.created_at >= window_start
            )
            count = db.exec(statement).one()
            if count >= limit:
                logger.warning(f"Velocity limit exceeded for OTP to {target}: {count} in {window_minutes}m")
                return False
        
        # Add more action types as needed (rental_attempt, login_failure, etc.)
        return True

    @staticmethod
    def is_blacklisted(db: Session, user_id: Optional[int] = None, phone: Optional[str] = None) -> bool:
        """
        Check if a user or phone number is in the system blacklist.
        """
        if user_id:
            block = db.exec(select(Blacklist).where(Blacklist.user_id == user_id, Blacklist.is_active == True)).first()
            if block: return True
            
        if phone:
            block = db.exec(select(Blacklist).where(Blacklist.identifier == phone, Blacklist.is_active == True)).first()
            if block: return True
            
        return False

    @staticmethod
    def add_to_blacklist(db: Session, identifier: str, reason: str, user_id: Optional[int] = None):
        """
        Manually add an identifier or user to the blacklist.
        """
        entry = Blacklist(
            identifier=identifier,
            user_id=user_id,
            reason=reason,
            is_active=True
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def calculate_risk_score(user_id: int) -> int:
        """
        Calculate fraud risk score for a user.
        0-100 scale, where 100 is confirmed fraud.
        Placeholder implementation.
        """
        logger.info(f"Calculating risk score for user {user_id} (Placeholder)")
        return 0
