from fastapi.testclient import TestClient
from app.main import app
import traceback
import sys

client = TestClient(app)
print("Testing admin login...")
try:
    response = client.post("/api/v1/auth/admin/login", json={
        "username": "admin@wezu.com",
        "password": "ChangeMe!Seed2026"
    })
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    traceback.print_exc()
