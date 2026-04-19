from __future__ import annotations
"""
Seed the test customer user:
  Email:    test@customer.com
  Password: Wezutest123
  Phone:    9154345918

Run: python seed_test_customer.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import engine
from sqlmodel import Session, select
from app.models.user import User, UserStatus
from app.core.security import get_password_hash

TEST_EMAIL = "test@customer.com"
TEST_PASSWORD = "Wezutest123"
TEST_PHONE = "9154345918"
TEST_NAME = "Test Customer"


def seed():
    with Session(engine) as db:
        # Check if already exists
        existing = db.exec(select(User).where(User.email == TEST_EMAIL)).first()
        if existing:
            # Update password and phone to make sure they match
            existing.hashed_password = get_password_hash(TEST_PASSWORD)
            existing.phone_number = TEST_PHONE
            existing.full_name = TEST_NAME
            existing.status = UserStatus.ACTIVE
            db.add(existing)
            db.commit()
            print(f"✅ Updated existing test customer (id={existing.id})")
            return

        user = User(
            email=TEST_EMAIL,
            phone_number=TEST_PHONE,
            full_name=TEST_NAME,
            hashed_password=get_password_hash(TEST_PASSWORD),
            user_type="customer",
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Created test customer (id={user.id})")
        print(f"   Email:    {TEST_EMAIL}")
        print(f"   Password: {TEST_PASSWORD}")
        print(f"   Phone:    {TEST_PHONE}")


if __name__ == "__main__":
    seed()
