import sys
import os
from sqlmodel import Session, create_engine, select, text

# Add parent directory to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.models.user import User, UserType, UserStatus
from app.models.financial import Wallet
from app.models.rbac import Role, UserRole
from app.core.security import get_password_hash

def reset_users():
    engine = create_engine(settings.DATABASE_URL)
    
    with Session(engine) as session:
        print("Cleaning up existing users and related data...")
        try:
            # Delete in order of constraints
            session.execute(text("DELETE FROM transactions"))
            session.execute(text("DELETE FROM rentals"))
            session.execute(text("DELETE FROM wallets"))
            session.execute(text("DELETE FROM user_roles"))
            session.execute(text("DELETE FROM user_profiles"))
            session.execute(text("DELETE FROM users"))
            session.commit()
            print("Cleanup successful.")
        except Exception as e:
            session.rollback()
            print(f"Error during cleanup: {e}")
            try:
                session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
                session.commit()
                print("Cleanup via TRUNCATE CASCADE successful.")
            except Exception as e2:
                session.rollback()
                print(f"Final cleanup failure: {e2}")

        print("Creating new user: laxmanlaxman1629@gmail.com")
        
        # Ensure CUSTOMER role exists
        customer_role = session.exec(select(Role).where(Role.name == "CUSTOMER")).first()
        if not customer_role:
            customer_role = Role(name="CUSTOMER", description="End Customer")
            session.add(customer_role)
            session.flush()

        # Create new user
        new_user = User(
            email="laxmanlaxman1629@gmail.com",
            phone_number="9154345918",
            hashed_password=get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")),
            full_name="Laxman Laxman",
            user_type=UserType.CUSTOMER,
            status=UserStatus.ACTIVE,
            role_id=customer_role.id
        )
        session.add(new_user)
        session.flush()

        # Assign role in UserRole table too for RBAC
        user_role = UserRole(user_id=new_user.id, role_id=customer_role.id)
        session.add(user_role)

        # Create wallet
        wallet = Wallet(
            user_id=new_user.id,
            balance=1000.0,
            currency="INR"
        )
        session.add(wallet)

        session.commit()
        print(f"User created successfully with ID: {new_user.id}")

if __name__ == "__main__":
    reset_users()
