import patch_utc
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select
from sqlalchemy import text
from app.db.session import engine
import app.models.all
from app.models.battery import Battery
from app.models.user import User
from app.models.dealer import DealerProfile
from app.core.security import get_password_hash

def fix_lax_to_wezu():
    with Session(engine) as db:
        print("Starting LAX -> WEZU Data Migration...")
        
        # 1. Update dealer user profile
        user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if user:
            print(f"Found user {user.email}, updating name and password...")
            user.full_name = "Wezu Dealer"
            user.hashed_password = get_password_hash("wezu123")
            db.add(user)
        else:
            print("Dealer user dealer@wezu.com not found!")
            
        # 2. Update dealer profile
        dealer = db.exec(select(DealerProfile).where(DealerProfile.contact_email == "dealer@wezu.com")).first()
        if dealer:
            print(f"Found dealer {dealer.business_name}, updating business name...")
            dealer.business_name = "Wezu Energy Solutions"
            db.add(dealer)
        else:
            print("Dealer profile for dealer@wezu.com not found!")

        # 3. Update all batteries (using raw SQL for speed)
        from sqlalchemy import text
        print("Executing bulk update for batteries...")
        db.exec(text("UPDATE core.batteries SET notes = 'seed_wezu_script', serial_number = REPLACE(serial_number, 'LAX-BATT-', 'WEZU-BATT-'), qr_code_data = REPLACE(qr_code_data, 'QR-LAX-', 'QR-WEZU-') WHERE notes = 'seed_laxman_script'"))
        
        try:
            db.commit()
            print("Successfully migrated LAX to WEZU entities.")
        except Exception as e:
            db.rollback()
            print(f"Error occurred during migration: {e}")

if __name__ == '__main__':
    fix_lax_to_wezu()
