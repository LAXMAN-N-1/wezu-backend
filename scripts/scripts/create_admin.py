"""
Create a superuser admin account.
Uses DATABASE_URL from environment / .env.

Usage:
    python scripts/create_admin.py                          # defaults
    python scripts/create_admin.py admin@wezu.com MyP@ss!   # custom
"""
import os
import sys
import secrets
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import app.main  # Fix SQLAlchemy mapper order

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.core.security import get_password_hash


def create_admin(email: str = "admin@wezu.com", password: str | None = None):
    if not password:
        password = secrets.token_urlsafe(16)
        print(f"Generated password (save it now, it won't be shown again): {password}")

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            superuser = User(
                email=email,
                full_name="Super Admin",
                hashed_password=get_password_hash(password),
                is_active=True,
                is_superuser=True
            )
            session.add(superuser)
            session.commit()
            print(f"Created admin user: {email}")
        else:
            print(f"Admin user already exists (id={user.id}), is_superuser={user.is_superuser}")


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@wezu.com"
    pwd = sys.argv[2] if len(sys.argv) > 2 else None
    create_admin(email, pwd)
