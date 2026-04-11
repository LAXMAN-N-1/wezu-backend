from fastapi.testclient import TestClient
from app.main import app
import sys
import traceback

client = TestClient(app)

print("Attempting login...")
try:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@wezu.com", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"Status: {response.status_code}")
    print(response.json())
except Exception as e:
    print("Caught Exception!")
    traceback.print_exc()
