from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select, func
from app.models.otp import OTP
from app.models.fraud import Blacklist
from typing import Optional, Dict, Any
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
    def calculate_risk_score(db: Session, user_id: int) -> Dict[str, Any]:
        """Calculate fraud risk score for a user using rule-based scoring.

        Score is 0-100 where 100 = confirmed fraud.
        Rules evaluated:
          - Blacklist hit:           +50
          - OTP velocity (>5 in 30m): +15
          - Multiple devices:        +10 per extra device (max +30)
          - Failed fraud checks:     +5 per recent failure (max +20)
        """
        score = 0
        breakdown: Dict[str, Any] = {}

        # Rule 1: Blacklist check
        is_blocked = FraudService.is_blacklisted(db, user_id=user_id)
        if is_blocked:
            score += 50
            breakdown["blacklist"] = {"hit": True, "points": 50}
        else:
            breakdown["blacklist"] = {"hit": False, "points": 0}

        # Rule 2: OTP velocity (>5 OTPs in last 30 minutes)
        from app.models.user import User
        user = db.get(User, user_id)
        if user and user.phone_number:
            window_start = datetime.now(UTC) - timedelta(minutes=30)
            otp_count = db.exec(
                select(func.count(OTP.id)).where(
                    OTP.target == user.phone_number,
                    OTP.created_at >= window_start,
                )
            ).one()
            otp_points = 15 if otp_count > 5 else 0
            score += otp_points
            breakdown["otp_velocity"] = {"count_30m": otp_count, "points": otp_points}
        else:
            breakdown["otp_velocity"] = {"count_30m": 0, "points": 0}

        # Rule 3: Multiple device fingerprints
        try:
            from app.models.device_fingerprint import DeviceFingerprint
            device_count = db.exec(
                select(func.count(DeviceFingerprint.id)).where(
                    DeviceFingerprint.user_id == user_id,
                )
            ).one()
            extra_devices = max(0, device_count - 1)
            device_points = min(extra_devices * 10, 30)
            score += device_points
            breakdown["device_fingerprints"] = {"total": device_count, "points": device_points}
        except Exception:
            breakdown["device_fingerprints"] = {"total": 0, "points": 0}

        # Rule 4: Recent failed fraud checks
        try:
            from app.models.fraud import FraudCheckLog
            recent_failures = db.exec(
                select(func.count(FraudCheckLog.id)).where(
                    FraudCheckLog.user_id == user_id,
                    FraudCheckLog.status == "FAIL",
                    FraudCheckLog.created_at >= datetime.now(UTC) - timedelta(days=30),
                )
            ).one()
            failure_points = min(recent_failures * 5, 20)
            score += failure_points
            breakdown["failed_checks_30d"] = {"count": recent_failures, "points": failure_points}
        except Exception:
            breakdown["failed_checks_30d"] = {"count": 0, "points": 0}

        # Cap at 100
        final_score = min(score, 100)

        # Determine risk level
        if final_score >= 70:
            risk_level = "CRITICAL"
        elif final_score >= 40:
            risk_level = "HIGH"
        elif final_score >= 15:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        logger.info(
            "FRAUD: Risk score calculated user_id=%s score=%d level=%s",
            user_id, final_score, risk_level,
        )

        return {
            "user_id": user_id,
            "score": final_score,
            "risk_level": risk_level,
            "breakdown": breakdown,
        }
