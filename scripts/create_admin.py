import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import app.main  # Fix SQLAlchemy mapper order

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.core.security import get_password_hash

def create_admin():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not user:
            superuser = User(
                email="admin@wezu.com",
                full_name="Super Admin",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_superuser=True
            )
            session.add(superuser)
            session.commit()
            print("Created admin user: admin@wezu.com / admin123")
        else:
            print(f"Admin user already exists (id={user.id}), is_superuser={user.is_superuser}")

if __name__ == "__main__":
    create_admin()
