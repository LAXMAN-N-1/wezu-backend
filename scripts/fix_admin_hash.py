"""Fix the admin user's corrupted password hash in the database."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User
from app.core.security import get_password_hash

def fix_admin_password():
    with Session(engine) as session:
        # Find admin user
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not user:
            print("❌ admin@wezu.com not found in database")
            return
        
        print(f"Found admin user: id={user.id}, email={user.email}")
        print(f"Current hash (first 30 chars): {user.hashed_password[:30] if user.hashed_password else 'NONE'}")
        
        # Generate a proper pbkdf2_sha256 hash for the password "laxman123"
        new_hash = get_password_hash("laxman123")
        print(f"New hash (first 30 chars): {new_hash[:30]}")
        
        user.hashed_password = new_hash
        session.add(user)
        session.commit()
        print("✅ Admin password hash fixed successfully!")

if __name__ == "__main__":
    fix_admin_password()
