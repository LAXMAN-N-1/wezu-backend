from fastapi.testclient import TestClient
import sys
import os

# Add the current directory to sys.path so 'app' can be imported
sys.path.append(os.getcwd())

from app.main import app
import json

client = TestClient(app)

print("Attempting login via TestClient...")
# We use the password from seed_data.py which I found earlier: "ChangeMe!Seed2026"
login_payload = {
    "username": "admin@wezu.com",
    "password": "ChangeMe!Seed2026"
}

try:
    response = client.post("/api/v1/auth/admin/login", json=login_payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("LOGIN SUCCESSFUL!")
    else:
        print("LOGIN FAILED. Checking database for user...")
        from sqlmodel import Session, select
        from app.db.session import engine
        from app.models.user import User
        with Session(engine) as db:
            user = db.exec(select(User).where(User.email == "admin@wezu.com")).first()
            if user:
                print(f"User exists: {user.email}, Role ID: {user.role_id}")
            else:
                print("User admin@wezu.com does NOT exist in DB.")
except Exception as e:
    import traceback
    traceback.print_exc()
