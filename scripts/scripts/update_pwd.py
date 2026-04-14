"""
Update a user's password in the database.
Uses DATABASE_URL from environment / .env — never hardcode credentials.

Usage:
    python scripts/update_pwd.py <email> <new_password>
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import get_password_hash
from app.models.user import User


def update_password(email: str, new_password: str):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            print(f"User {email} not found in the database.")
            return False

        user.hashed_password = get_password_hash(new_password)
        session.add(user)
        session.commit()
        print(f"Successfully updated password for {email}.")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/update_pwd.py <email> <new_password>")
        sys.exit(1)
    update_password(sys.argv[1], sys.argv[2])
