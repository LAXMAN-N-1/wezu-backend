from __future__ import annotations
import asyncio
import os
import random
import uuid
import uuid
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
import faker
from passlib.context import CryptContext

import psycopg2
from app.core.config import settings

fake = faker.Faker('en_IN')
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_URL = str(settings.DATABASE_URL).replace("+asyncpg", "")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    # 1. Clear existing generated users (optional - just to keep it clean, maybe just insert new ones)
    # We will generate new ones.

    print("Generating Roles...")
    roles = [
        ("Superadmin", "Full system access"),
        ("Support Agent", "Can manage tickets and users"),
        ("Manager", "Can view analytics and manage fleet"),
        ("Marketing", "Can manage promos and communications")
    ]
    role_ids = []
    for name, desc in roles:
        cursor.execute("SELECT id FROM roles WHERE name = %s", (name,))
        res = cursor.fetchone()
        if res:
            role_ids.append(res[0])
        else:
            cursor.execute("INSERT INTO roles (name, description, category, level, is_system_role, is_active) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", (name, desc, "system", 1, True, True))
            role_ids.append(cursor.fetchone()[0])
            
    print("Populating 50 Users...")
    user_types = ["CUSTOMER", "CUSTOMER", "CUSTOMER", "CUSTOMER", "DEALER", "ADMIN", "SUPPORT_AGENT", "LOGISTICS"]
    statuses = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "SUSPENDED", "PENDING_VERIFICATION"]
    kyc_statuses = ["NOT_SUBMITTED", "PENDING", "APPROVED", "REJECTED"]
    
    users = []
    
    # Bulk insert users using raw sql to avoid enum issues
    for i in range(50):
        # random user
        full_name = fake.name()
        email = fake.unique.email()
        phone = fake.unique.phone_number()[:15]
        u_type = random.choice(user_types)
        status = random.choice(statuses)
        kyc = random.choice(kyc_statuses)
        
        is_superuser = (u_type == "ADMIN")
        created_at = fake.date_time_between(start_date="-1y", end_date="now")
        updated_at = created_at + timedelta(days=random.randint(1, 30))
        
        hashed = get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026"))
        
        role_id = random.choice(role_ids) if u_type in ["ADMIN", "SUPPORT_AGENT", "LOGISTICS"] else None
        
        cursor.execute("""
            INSERT INTO users (
                phone_number, email, full_name, hashed_password, user_type, status,
                is_superuser, role_id, kyc_status, is_email_verified, created_at, updated_at,
                two_factor_enabled, is_deleted
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (phone, email, full_name, hashed, u_type, status, is_superuser, role_id, kyc, True, created_at, updated_at, False, False))
        u_id = cursor.fetchone()[0]
        users.append({
            "id": u_id,
            "kyc_status": kyc
        })

    print(f"Generated 50 users.")
    
    print("Generating KYC Documents for Pending/Approved/Rejected users...")
    doc_types = ["AADHAAR", "PAN", "DRIVING_LICENSE"]
    for u in users:
        if u["kyc_status"] != "NOT_SUBMITTED":
            num_docs = random.randint(1, 2)
            for _ in range(num_docs):
                dtype = random.choice(doc_types)
                doc_num = fake.ssn() if dtype in ["aadhaar", "pan"] else fake.license_plate()
                
                status_map = {
                    "PENDING": "PENDING",
                    "APPROVED": "VERIFIED",
                    "REJECTED": "REJECTED"
                }
                d_status = status_map[u["kyc_status"]]
                
                reason = "Blurry image" if d_status == "REJECTED" else None
                
                cursor.execute("""
                    INSERT INTO kyc_documents (
                        user_id, document_type, document_number, file_url,
                        status, rejection_reason, uploaded_at, verified_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    u["id"], dtype, doc_num, f"https://mock-s3.wezu.in/docs/{uuid.uuid4()}.jpg",
                    d_status, reason, datetime.now(UTC) - timedelta(days=5),
                    datetime.now(UTC) if d_status != "PENDING" else None
                ))
    print("Generated KYC Documents.")
    
    print("User population complete!")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
