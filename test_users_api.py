import asyncio
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.db.session import engine
from app.models.user import User

client = TestClient(app)

def test_apis():
    with Session(engine) as db:
        admin_user = db.exec(select(User).where(User.user_type == "ADMIN")).first()
        if not admin_user:
            print("No admin user found.")
            return

    from app.core.security import create_access_token
    from datetime import timedelta
    token = create_access_token(admin_user.id, expires_delta=timedelta(minutes=60))
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Testing /api/v1/admin/users/")
    resp1 = client.get("/api/v1/admin/users/", headers=headers)
    print("Users Status:", resp1.status_code)
    print("Total Users:", resp1.json().get('total_count') if resp1.status_code == 200 else resp1.text)

    print("\nTesting /api/v1/admin/users/suspended")
    resp2 = client.get("/api/v1/admin/users/suspended", headers=headers)
    print("Suspended Status:", resp2.status_code)
    print("Total Suspended:", resp2.json().get('total_count') if resp2.status_code == 200 else resp2.text)

    print("\nTesting /api/v1/admin/kyc/documents")
    resp3 = client.get("/api/v1/admin/kyc/documents", headers=headers)
    print("KYC Docs Status:", resp3.status_code)
    print("Total KYC Docs:", resp3.json().get('total_count') if resp3.status_code == 200 else resp3.text)

    print("\nTesting /api/v1/admin/roles/")
    resp4 = client.get("/api/v1/admin/roles/", headers=headers)
    print("Roles Status:", resp4.status_code)
    print("Roles Count:", len(resp4.json()) if resp4.status_code == 200 else resp4.text)

if __name__ == "__main__":
    test_apis()
