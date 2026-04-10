
import os
import sys
from sqlmodel import Session, select

# Add parent dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import ALL models to ensure they are in the registry
import app.models.all

from app.db.session import engine
from app.models.user import User
from app.core.security import get_password_hash

def fix_password():
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if user:
            print(f"Fixing password for user: {user.email}")
            new_hash = get_password_hash("laxman123")
            print(f"New hash: {new_hash[:10]}...")
            user.hashed_password = new_hash
            db.add(user)
            db.commit()
            print("Password updated successfully.")
        else:
            print("User dealer@wezu.com not found.")

if __name__ == "__main__":
    fix_password()
