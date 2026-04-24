import patch_utc
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from app.db.session import engine
import app.models.all
from app.models.fraud import RiskScore, FraudCheckLog, Blacklist
from app.models.user import User, UserType

def seed_fraud_data():
    with Session(engine) as db:
        print("Starting Fraud Data Seeding...")
        
        # 1. Seed Blacklists
        print("Seeding Blacklists...")
        blacklist_entries = [
            Blacklist(type="IP", value="192.168.1.100", reason="Known botnet IP"),
            Blacklist(type="PHONE", value="9999999999", reason="Known scammer phone number"),
            Blacklist(type="DEVICE_ID", value="DEVICE_ABC_123", reason="Device associated with chargebacks"),
            Blacklist(type="PAN", value="ABCDE1234F", reason="Fraudulent PAN card"),
            Blacklist(type="EMAIL", value="scammer@example.com", reason="Throwaway email domain")
        ]
        
        for entry in blacklist_entries:
            # Check if it already exists to be idempotent
            existing = db.exec(select(Blacklist).where(Blacklist.value == entry.value)).first()
            if not existing:
                db.add(entry)
                
        # 2. Extract some users to assign risk scores and fraud logs
        # Grab up to 3 regular users
        sample_users = db.exec(select(User).where(User.user_type == UserType.CUSTOMER).limit(3)).all()
        # If no customer, just get any users
        if not sample_users:
            sample_users = db.exec(select(User).limit(3)).all()
            
        print(f"Assigning RiskScores to {len(sample_users)} users...")
        for i, user in enumerate(sample_users):
            # Seed RiskScore
            existing_score = db.exec(select(RiskScore).where(RiskScore.user_id == user.id)).first()
            if not existing_score:
                risk_score_val = 15.0 * (i + 1) # Variable risk
                score = RiskScore(
                    user_id=user.id,
                    total_score=risk_score_val,
                    breakdown={
                        "ip_risk": risk_score_val / 3,
                        "device_risk": risk_score_val / 3,
                        "velocity_risk": risk_score_val / 3
                    }
                )
                db.add(score)
            else:
                existing_score.total_score = 15.0 * (i + 1)
                db.add(existing_score)
                
            # Seed Fraud Check Logs
            logs = [
                FraudCheckLog(user_id=user.id, check_type="IP_CHECK", status="WARN", details="IP slightly anomalous"),
                FraudCheckLog(user_id=user.id, check_type="DEVICE_FINGERPRINT", status="PASS", details="Device fingerprint matches history"),
            ]
            # Add a FAIL log to the highest risk user
            if i == len(sample_users) - 1:
                logs.append(FraudCheckLog(user_id=user.id, check_type="PAN_VERIFY", status="FAIL", details="PAN mismatch with external database"))
            
            for log in logs:
                db.add(log)
                
        try:
            db.commit()
            print("Successfully seeded Fraud data.")
        except Exception as e:
            db.rollback()
            print(f"Error occurred during fraud data seeding: {e}")

if __name__ == '__main__':
    seed_fraud_data()
