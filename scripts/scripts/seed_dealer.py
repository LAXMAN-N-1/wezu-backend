import os
import sys

# Add the backend app to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.db.session import engine
from app.models.dealer import DealerProfile
from app.models.user import User

def seed_dealer():
    with Session(engine) as db:
        # Find dealer user
        dealer_user = db.exec(select(User).where(User.email == 'dealer@wezu.com')).first()
        if not dealer_user:
            print("Dealer user not found")
            return
            
        print(f"Found dealer user with id {dealer_user.id}")
        
        # Check if DealerProfile exists
        profile = db.exec(select(DealerProfile).where(DealerProfile.user_id == dealer_user.id)).first()
        
        if not profile:
            print("Creating DealerProfile...")
            profile = DealerProfile(
                user_id=dealer_user.id,
                business_name="Hyderabad Dealer Corp",
                contact_person="Laxman",
                contact_email="dealer@wezu.com",
                contact_phone="8888888888",
                address_line1="Madhapur, Hyderabad",
                city="Hyderabad",
                state="Telangana",
                pincode="500081",
                gst_number="GSTIN123456789",
                is_active=True
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            print(f"Created DealerProfile with id {profile.id}")
        else:
            print(f"DealerProfile already exists with id {profile.id}")
            profile.is_active = True
            db.add(profile)
            db.commit()

if __name__ == "__main__":
    seed_dealer()
