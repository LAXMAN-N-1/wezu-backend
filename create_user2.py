import asyncio
from httpx import AsyncClient
from app.main import app
from app.db.session import engine
from sqlmodel import Session, select
from app.models.user import User, UserStatus
from app.models.rbac import Role
from app.core.security import get_password_hash
import uuid

def create_user_direct():
    with Session(engine) as session:
        phone = "7007297384"
        
        # Check if already exists
        existing = session.exec(select(User).where(User.phone_number == phone)).first()
        if existing:
            print("User already exists. Updating details...")
            existing.full_name = "bindu"
            existing.hashed_password = get_password_hash("123456789")
            existing.status = UserStatus.ACTIVE
            session.add(existing)
            session.commit()
            print("User updated successfully.")
            return

        print("Creating User...")
        # Get Customer Role
        customer_role = session.exec(select(Role).where(Role.name == "customer")).first()
        
        # Create new user
        user = User(
            full_name="bindu",
            phone_number=phone,
            hashed_password=get_password_hash("123456789"),
            status=UserStatus.ACTIVE,
            kyc_status="verified",
            role=customer_role,
            # FIlling in mandatory fields
            company_name="Bindu Individual",
            gst_number=f"GST{str(uuid.uuid4())[:10].upper()}",
            business_type="individual",
            is_email_verified=False
        )
        
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"User created successfully: ID {user.id}, Name: {user.full_name}, Phone: {user.phone_number}")

if __name__ == "__main__":
    create_user_direct()
