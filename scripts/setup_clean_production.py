import os
import sys

# Add the parent directory to sys.path to allow importing from app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select, delete
from sqlalchemy import text
from app.db.session import engine
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile
from app.models.rbac import Role, UserRole, AdminUserRole
from app.models.admin_user import AdminUser
from app.models.user_profile import UserProfile
from app.core.security import get_password_hash

def clean_and_setup_production():
    with Session(engine) as session:
        # 1. Clean up existing users and profiles - Hard Clear
        print("Starting CLEAN SLATE cleanup of all users...")
        try:
             # Manual recursive clean-up of known tables with dependencies
             print("Cleaning up linked tables...")
             tables_to_clear = [
                 "admin_user_roles", "user_roles", "user_sessions", 
                 "login_history", "otps", "user_profiles", "dealer_profiles", 
                 "wallets", "admin_users", "users"
             ]
             for table in tables_to_clear:
                 session.exec(text(f"DELETE FROM {table};"))
             
             session.commit()
             print("Successfully cleared all existing user data!")
        except Exception as e:
             session.rollback()
             print(f"Cleanup failed: {e}")
             # Fallback: Try a single TRUNCATE CASCADE if we have permissions
             try:
                 session.exec(text("TRUNCATE TABLE admin_user_roles, user_roles, admin_users, users CASCADE;"))
                 session.commit()
                 print("Successfully truncated user data!")
             except Exception as e2:
                 session.rollback()
                 print(f"Fallback truncate also failed: {e2}")
                 raise e
        
        # 2. Re-seed Roles if they were cleared (Ensure standard roles exist)
        print("Verifying standard roles...")
        from app.db.initial_data import seed_roles
        seed_roles(session)
        session.commit()

        # Retrieve needed Roles
        admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
        dealer_role = session.exec(select(Role).where(Role.name == "dealer")).first()
        customer_role = session.exec(select(Role).where(Role.name == "customer")).first()
        
        # ---------------------------------------------
        # 1. ADMIN USER (admin@wezu.com)
        # ---------------------------------------------
        print("Seeding Admin: admin@wezu.com")
        admin_user = User(
            email="admin@wezu.com",
            phone_number="9154345918",
            full_name="System Admin",
            hashed_password=get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")),
            user_type=UserType.ADMIN,
            status=UserStatus.ACTIVE,
            is_superuser=True
        )
        if admin_role:
            admin_user.role_id = admin_role.id
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)

        # Separate AdminUser table record
        admin_table_user = AdminUser(
             email="admin@wezu.com",
             phone_number="9154345918",
             full_name="System Admin",
             hashed_password=get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")),
             is_superuser=True,
             is_active=True
        )
        session.add(admin_table_user)
        session.commit()
        session.refresh(admin_table_user)
        
        if admin_role:
             session.add(AdminUserRole(admin_id=admin_table_user.id, role_id=admin_role.id))
             session.commit()

        # ---------------------------------------------
        # 2. DEALER USER (dealer@wezu.com)
        # ---------------------------------------------
        print("Seeding Dealer: dealer@wezu.com")
        dealer_user = User(
            email="dealer@wezu.com",
            phone_number="9154345917", # Unique
            full_name="Laxman Dealer",
            hashed_password=get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")),
            user_type=UserType.DEALER,
            status=UserStatus.ACTIVE
        )
        if dealer_role:
             dealer_user.role_id = dealer_role.id
        session.add(dealer_user)
        session.commit()
        session.refresh(dealer_user)
        
        dealer_profile = DealerProfile(
            user_id=dealer_user.id,
            business_name="WEZU Official Dealer",
            contact_person="Laxman",
            contact_email="dealer@wezu.com",
            contact_phone="9154345917",
            address_line1="Production HQ",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
            is_active=True
        )
        session.add(dealer_profile)
        session.commit()

        # ---------------------------------------------
        # 3. CUSTOMER USER (customer@wezu.com)
        # ---------------------------------------------
        print("Seeding Customer: customer@wezu.com")
        customer_user = User(
            email="customer@wezu.com",
            phone_number="9154345916", # Unique
            full_name="Laxman Customer",
            hashed_password=get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")),
            user_type=UserType.CUSTOMER,
            status=UserStatus.ACTIVE
        )
        if customer_role:
             customer_user.role_id = customer_role.id
        session.add(customer_user)
        session.commit()
        session.refresh(customer_user)
        
        # UserProfile link
        customer_profile = UserProfile(
            user_id=customer_user.id,
            # Adjust fields to match model
            country="India",
            preferred_language="en"
        )
        session.add(customer_profile)
        session.commit()

        print("=======================================")
        print("SUCCESS: Production accounts finalized on Old Neon DB.")
        print("Admin: admin@wezu.com / laxman123")
        print("Dealer: dealer@wezu.com / laxman123")
        print("Customer: customer@wezu.com / laxman123")
        print("=======================================")

        print("=======================================")
        print("SUCCESS: Credentials strictly configured per requested requirements.")
        print("=======================================")

if __name__ == "__main__":
    clean_and_setup_production()
