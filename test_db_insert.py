import asyncio
from httpx import AsyncClient
from app.main import app
from app.db.session import engine
from sqlmodel import Session, select, text
from app.models.user import User, UserStatus
from app.models.rbac import Role
from app.core.security import get_password_hash

def run_insert():
    with Session(engine) as session:
        phone = "7007297384"
        password_hash = get_password_hash("123456789")
        
        # 1. Check if user exists in core.users
        existing_user = session.exec(select(User).where(User.phone_number == phone)).first()
        
        if existing_user:
            print(f"User already exists in core.users with ID: {existing_user.id}")
            existing_user.full_name = "bindu"
            existing_user.hashed_password = password_hash
            existing_user.status = UserStatus.ACTIVE
            session.add(existing_user)
            session.commit()
            print("Core User updated.")
            user_id = existing_user.id
        else:
            print("Creating core User...")
            customer_role = session.exec(select(Role).where(Role.name == "customer")).first()
            role_id = customer_role.id if customer_role else 2
            
            # Using raw SQL for core.users to avoid ORM confusion
            insert_core = text("""
                INSERT INTO core.users (
                    phone_number, full_name, hashed_password, status, user_type, role_id, 
                    is_superuser, kyc_status, two_factor_enabled, is_email_verified, is_deleted,
                    created_at, updated_at
                ) VALUES (
                    :phone, :name, :hash, 'ACTIVE', 'CUSTOMER', :role,
                    false, 'APPROVED', false, false, false,
                    NOW(), NOW()
                ) RETURNING id;
            """)
            result = session.exec(insert_core, params={"phone": phone, "name": "bindu", "hash": password_hash, "role": role_id})
            user_id = result.first()[0]
            session.commit()
            print(f"Created core User with ID: {user_id}")
            
        # 2. Upsert into public.users (the customer table)
        print("Upserting into public.users...")
        insert_public = text("""
            INSERT INTO public.users (
                id, phone_number, full_name, hashed_password, status, user_type, role_id, 
                is_superuser, kyc_status, two_factor_enabled, created_at, updated_at
            )
            VALUES (
                :id, :phone, :name, :hash, 'ACTIVE', 'CUSTOMER', :role,
                false, 'APPROVED', false, NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET updated_at = NOW();
        """)
        session.exec(insert_public, params={
            "id": user_id, 
            "phone": phone, 
            "name": "bindu", 
            "hash": password_hash, 
            "role": existing_user.role_id if existing_user else 2
        })
        session.commit()
        print(f"Successfully Upserted public.users for ID: {user_id}")

        
if __name__ == "__main__":
    run_insert()
