import asyncio
from httpx import AsyncClient
from app.main import app
from app.db.session import engine
from sqlmodel import Session, select
from app.models.customer import Customer
from app.models.user import UserStatus
from app.models.rbac import Role
from app.core.security import get_password_hash
import uuid

def create_customer_direct():
    with Session(engine) as session:
        phone = "7007297384"
        
        # Check if already exists
        existing = session.exec(select(Customer).where(Customer.phone_number == phone)).first()
        if existing:
            print("Customer already exists. Updating details...")
            existing.full_name = "bindu"
            existing.hashed_password = get_password_hash("123456789")
            existing.status = UserStatus.ACTIVE
            session.add(existing)
            session.commit()
            print("Customer updated successfully.")
            return

        print("Creating Customer...")
        # Get Customer Role
        customer_role = session.exec(select(Role).where(Role.name == "customer")).first()
        
        # Create new customer
        customer = Customer(
            full_name="bindu",
            phone_number=phone,
            hashed_password=get_password_hash("123456789"),
            status=UserStatus.ACTIVE,
            kyc_status="verified",
            role_id=customer_role.id if customer_role else 2,
            company_name="none",
            business_type="individual",
            is_email_verified=False
        )
        
        session.add(customer)
        session.commit()
        session.refresh(customer)
        print(f"Customer created successfully: ID {customer.id}, Name: {customer.full_name}, Phone: {customer.phone_number}")

if __name__ == "__main__":
    create_customer_direct()
