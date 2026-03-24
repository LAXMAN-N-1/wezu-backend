import sys
import os
from datetime import datetime
import uuid

# Add the parent directory to sys.path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import get_password_hash
from app.models.user import User, UserType, UserStatus, KYCStatus
from app.models.user_profile import UserProfile
from app.models.financial import Wallet

def create_user():
    email = "wezu@gmail.com"
    phone = "987654321"
    password = "wezutech"
    role_id = 64 # CUSTOMER role as verified
    
    with Session(engine) as session:
        # Check if user already exists
        new_user = session.exec(
            select(User).where((User.email == email) | (User.phone_number == phone))
        ).first()
        
        if not new_user:
            print(f"Creating user: {email}...")
            # 1. Create User
            new_user = User(
                email=email,
                phone_number=phone,
                hashed_password=get_password_hash(password),
                user_type=UserType.CUSTOMER,
                status=UserStatus.ACTIVE,
                role_id=role_id,
                kyc_status=KYCStatus.NOT_SUBMITTED,
                full_name="Wezu Tech"
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            print(f"User created with ID: {new_user.id}")
        else:
            print(f"User {email} already exists with ID: {new_user.id}")

        # Check/Create UserProfile
        existing_profile = session.exec(select(UserProfile).where(UserProfile.user_id == new_user.id)).first()
        if not existing_profile:
            print(f"Creating profile for user {new_user.id}...")
            new_profile = UserProfile(
                user_id=new_user.id,
                id=None,
                city="Hyderabad",
                country="India",
                preferred_language="en"
            )
            session.add(new_profile)
        else:
            print(f"Profile already exists for user {new_user.id}")
        
        # Check/Create Wallet
        existing_wallet = session.exec(select(Wallet).where(Wallet.user_id == new_user.id)).first()
        if not existing_wallet:
            print(f"Creating wallet for user {new_user.id}...")
            new_wallet = Wallet(
                user_id=new_user.id,
                id=None,
                balance=0.0,
                currency="INR"
            )
            session.add(new_wallet)
        else:
            print(f"Wallet already exists for user {new_user.id}")
        
        session.commit()
        print(f"Profile and Wallet created for user {new_user.id}.")
        print("Done!")

if __name__ == "__main__":
    create_user()
