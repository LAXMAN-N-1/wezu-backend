
import os
import sys
from sqlmodel import Session, select

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.db.session import engine
from app.models.user import User

def check_dealer_hash():
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if user:
            print(f"User ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Hashed Password: {user.hashed_password}")
            if user.hashed_password:
                print(f"Hash starts with: {user.hashed_password[:10]}...")
            else:
                print("Hash is NULL/None")
        else:
            print("User not found")

if __name__ == "__main__":
    check_dealer_hash()
