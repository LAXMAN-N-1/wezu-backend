import sys
import os
from sqlmodel import Session, select

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.core.database import engine
from app.models.user import User

def check_admin():
    with Session(engine) as session:
        statement = select(User).where(User.email == "admin@wezu.com")
        user = session.exec(statement).first()
        if user:
            print(f"User found: {user.email}")
            print(f"Is active: {user.is_active}")
            print(f"Is superuser: {user.is_superuser}")
            print(f"Has password: {user.hashed_password is not None}")
        else:
            print("User admin@wezu.com NOT found in database.")

if __name__ == "__main__":
    check_admin()
