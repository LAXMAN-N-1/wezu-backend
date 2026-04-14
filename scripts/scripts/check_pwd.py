"""
Check password hashes in the database.
Uses DATABASE_URL from environment / .env — never hardcode credentials.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import verify_password
from app.models.user import User


def check_password(email: str, test_passwords: list[str]):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or not user.hashed_password:
            print(f"User {email} not found or has no password.")
            return

        for p in test_passwords:
            if verify_password(p, user.hashed_password):
                print(f"MATCH FOUND for {email}: {p}")
                return
        print(f"No matching password found for {email}.")


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@wezu.com"
    check_password(email, ["password", "password123", "admin123"])
