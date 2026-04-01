"""
List dealer users in the database.
Uses DATABASE_URL from environment / .env — never hardcode credentials.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User


def list_dealers():
    with Session(engine) as session:
        users = session.exec(
            select(User).where(User.user_type == "dealer")
        ).all()
        print("Dealers in DB:")
        for u in users:
            print(f"  {u.email}  |  {u.full_name}  |  {u.user_type}")
        if not users:
            print("  (none)")


if __name__ == "__main__":
    list_dealers()
