import sys
import os

# Add backend directory to sys path if not there
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
import app.models.all
from app.models.user import User
from sqlmodel import select

db = SessionLocal()
try:
    # Use select() which is the SQLModel way
    statement = select(User)
    users = db.exec(statement).all()
    print("=== ALL USERS ===")
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}, Phone: {u.phone_number}, User Type: {u.user_type}, Status: {u.status}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
