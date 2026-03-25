from datetime import datetime, timedelta
from sqlmodel import Session, select, func, col
from app.models.otp import OTP
from app.models.fraud import Blacklist
from app.models.user import User
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
            window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
            statement = select(func.count(col(OTP.id))).where(
                col(OTP.target) == target,
                col(OTP.created_at) >= window_start
            )
            count = db.exec(statement).one() or 0
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
            user = db.get(User, user_id)
            if user:
                if user.email:
                    if db.exec(select(Blacklist).where(col(Blacklist.type) == "EMAIL", col(Blacklist.value) == user.email)).first():
                        return True
                if user.phone_number:
                    if db.exec(select(Blacklist).where(col(Blacklist.type) == "PHONE", col(Blacklist.value) == user.phone_number)).first():
                        return True
            
        if phone:
            block = db.exec(select(Blacklist).where(col(Blacklist.value) == phone)).first()
            if block: return True
            
        return False

    @staticmethod
    def add_to_blacklist(db: Session, block_type: str, value: str, reason: str):
        """
        Manually add an identifier to the blacklist.
        block_type: PHONE, EMAIL, IP, DEVICE_ID, PAN
        """
        entry = Blacklist(
            type=block_type,
            value=value,
            reason=reason
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
