import asyncio
from sqlmodel import Session
from app.db.session import engine
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile, DealerApplication
from app.models.rbac import Role
from app.core.security import get_password_hash
from sqlmodel import select
from datetime import datetime

def create_test_dealer():
    db = Session(engine)
    try:
        # Check if dealer already exists
        existing = db.execute(select(User).where(User.email == "dealer@wezutech.com")).first()
        if existing:
            print("Dealer already exists!")
            return

        # Create User
        user = User(
            email="dealer@wezutech.com",
            phone_number="9876543210",
            full_name="WEZU Test Dealer",
            hashed_password=get_password_hash("WezuDealer2024!"),
            user_type=UserType.DEALER,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Assign Role
        dealer_role = db.execute(select(Role).where(Role.name == "dealer")).scalar_one_or_none()
        if dealer_role:
            user.role_id = dealer_role.id
            db.add(user)
            db.commit()

        # Create Dealer Profile
        profile = DealerProfile(
            user_id=user.id,
            business_name="WEZU Official Dealer",
            contact_person="Ramesh Kumar",
            contact_email="dealer@wezutech.com",
            contact_phone="9876543210",
            address_line1="Bala Nagar Industrial Area",
            city="Hyderabad",
            state="Telangana",
            pincode="500037",
            is_active=True,  # Auto-approve for testing
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # Create Application
        application = DealerApplication(
            dealer_id=profile.id,
            current_stage="APPROVED",
            status_history=[{
                "stage": "APPROVED",
                "timestamp": str(datetime.utcnow()),
                "note": "Auto-approved test account",
            }],
        )
        db.add(application)
        db.commit()
        
        print("Success! Dealer created.")
        print("Email: dealer@wezutech.com")
        print("Password: WezuDealer2024!")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_dealer()
