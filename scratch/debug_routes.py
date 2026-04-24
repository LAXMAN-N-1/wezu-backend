from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
resp = client.get("/debug-routes")
print(resp.json()["routes"])
