from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
print("Testing getting user list...")
response = client.get("/api/v1/admin/users/")
print("Status:", response.status_code)
if response.status_code == 500:
    print("Response:", response.text)
