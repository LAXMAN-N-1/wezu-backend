from sqlmodel import Session, select
from app.core.database import engine
from app.models.fraud import RiskScore, FraudCheckLog, Blacklist
from app.models.user import User
from datetime import datetime
import random

class FraudService:
    
    @staticmethod
    def calculate_risk_score(user_id: int) -> float:
        with Session(engine) as session:
            score = 0
            breakdown = {}
            
            user = session.get(User, user_id)
            if not user:
                 return 0
                 
            # 1. Profile Completeness
            if not user.email or not user.phone_number:
                score += 20
                breakdown["profile_incomplete"] = 20
            
            # 2. Blacklist Check
            blacklist_hit = session.exec(select(Blacklist).where(Blacklist.value.in_([user.email, user.phone_number]))).first()
            if blacklist_hit:
                score += 100
                breakdown["blacklist"] = 100
                
            # 3. Mock External Fraud API
            # if user.phone_number.startswith("999"): score += 50
            
            # Update DB
            risk_entry = session.exec(select(RiskScore).where(RiskScore.user_id == user_id)).first()
            if not risk_entry:
                risk_entry = RiskScore(user_id=user_id)
            
            risk_entry.total_score = min(score, 100)
            risk_entry.breakdown = breakdown
            risk_entry.last_updated = datetime.utcnow()
            
            session.add(risk_entry)
            session.commit()
            return risk_entry.total_score

    @staticmethod
    def get_risk_score(user_id: int):
        with Session(engine) as session:
            return session.exec(select(RiskScore).where(RiskScore.user_id == user_id)).first()

    @staticmethod
    def log_check(user_id: int, check_type: str, status: str, details: str = ""):
        with Session(engine) as session:
            log = FraudCheckLog(
                user_id=user_id,
                check_type=check_type,
                status=status,
                details=details
            )
            session.add(log)
            session.commit()
