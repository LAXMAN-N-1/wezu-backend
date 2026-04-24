import os
import sys

# Add the parent directory to sys.path to allow importing from app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User, UserType
from app.models.admin_user import AdminUser
from app.models.dealer import DealerProfile
from app.models.user_profile import UserProfile

def verify():
    with Session(engine) as session:
        print("--- VERIFYING PRODUCTION DATA ---")
        
        # 1. Users table
        users = session.exec(select(User)).all()
        print(f"Total Users: {len(users)}")
        for u in users:
            print(f"- {u.email} | Type: {u.user_type} | Phone: {u.phone_number} | Role ID: {u.role_id}")
            
        # 2. Admin Users table
        admins = session.exec(select(AdminUser)).all()
        print(f"\nTotal AdminUsers Record (Separate Table): {len(admins)}")
        for a in admins:
            print(f"- {a.email} | Superuser: {a.is_superuser}")
            
        # 3. Profiles
        dealer_profiles = session.exec(select(DealerProfile)).all()
        print(f"\nDealer Profiles: {len(dealer_profiles)}")
        for d in dealer_profiles:
            print(f"- Business: {d.business_name} | Contact: {d.contact_email}")
            
        user_profiles = session.exec(select(UserProfile)).all()
        print(f"\nUser Profiles Attached: {len(user_profiles)}")
        for p in user_profiles:
            print(f"- User ID: {p.user_id}")

        print("\n--- END OF VERIFICATION ---")

if __name__ == "__main__":
    verify()
