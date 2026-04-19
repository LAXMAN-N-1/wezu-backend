from __future__ import annotations
"""
Seed the test dealer user:
  Email:    test@test.com
  Password: test

Run: python seed_test_dealer.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import engine
from sqlmodel import Session, select
from app.models.user import User, UserStatus
from app.models.dealer import DealerProfile
from app.core.security import get_password_hash

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test"
TEST_PHONE = "0000000000"
TEST_NAME = "Test Dealer"

def seed():
    with Session(engine) as db:
        existing = db.exec(select(User).where(User.email == TEST_EMAIL)).first()
        if existing:
            existing.hashed_password = get_password_hash(TEST_PASSWORD)
            existing.user_type = "dealer"
            existing.status = UserStatus.ACTIVE
            db.add(existing)
            db.commit()
            print(f"✅ Updated existing test dealer (id={existing.id})")
            user_record = existing
        else:
            user = User(
                email=TEST_EMAIL,
                phone_number=TEST_PHONE,
                full_name=TEST_NAME,
                hashed_password=get_password_hash(TEST_PASSWORD),
                user_type="dealer",
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Created test dealer (id={user.id})")
            user_record = user
        
        dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == user_record.id)).first()
        if not dealer:
            dealer_profile = DealerProfile(
                user_id=user_record.id,
                business_name="Test Business",
                contact_person=TEST_NAME,
                contact_email=TEST_EMAIL,
                contact_phone=TEST_PHONE,
                address_line1="Test Address",
                city="Test City",
                state="Test State",
                pincode="111111"
            )
            db.add(dealer_profile)
            db.commit()
            print(f"✅ Created DealerProfile for test dealer")
        else:
            print(f"✅ DealerProfile already exists for test dealer")

if __name__ == "__main__":
    seed()
