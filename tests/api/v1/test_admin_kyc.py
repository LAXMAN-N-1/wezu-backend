from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.user import User
from app.models.kyc import KYCDocument
import random

def get_auth_headers(client: TestClient, email: str = "kyc_user@test.com"):
    # Generate unique phone based on email hash or random to avoid collision
    random_phone = f"{random.randint(1000000000, 9999999999)}"
    
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "KYC User",
            "phone_number": random_phone
        },
    )
    
    # 2. Login
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": "Password123!"
        },
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

def test_get_kyc_queue(client: TestClient, session: Session):
    # 1. Setup: Create a user with pending KYC
    email = "pending_kyc_user@test.com"
    # Register & Login to get token
    headers = get_auth_headers(client, email=email)
    
    # Update user status to pending_verification manually for speed
    user = session.exec(select(User).where(User.email == email)).first()
    user.kyc_status = "pending"
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create dummy documents
    doc1 = KYCDocument(
        user_id=user.id,
        document_type="aadhaar",
        file_url="http://s3/aadhaar.jpg",
        status="pending",
        metadata_='{"side": "front"}'
    )
    session.add(doc1)
    session.commit()
    
    # 2. Authenticate as Admin
    su_email = "admin_kyc@test.com"
    su_headers = get_auth_headers(client, email=su_email)
    
    # Promote to SU
    su_user = session.exec(select(User).where(User.email == su_email)).first()
    su_user.is_superuser = True
    session.add(su_user)
    session.commit()
    
    # 3. Call Endpoint
    resp = client.get("/api/v1/admin/kyc/pending", headers=su_headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # 4. Verify Response
    assert data["total"] >= 1
    items = data["items"]
    found = False
    for item in items:
        if item["email"] == email:
            found = True
            assert item["user_id"] == user.id
            assert len(item["documents"]) >= 1
            assert item["documents"][0]["document_type"] == "aadhaar"
    
    assert found

def test_verify_kyc_submission(client: TestClient, session: Session):
    # 1. Setup: User with pending KYC
    email = "verify_kyc_user@test.com"
    headers = get_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.kyc_status = "pending"
    session.add(user)
    session.commit()
    
    doc = KYCDocument(
        user_id=user.id,
        document_type="pan",
        file_url="http://s3/pan.jpg",
        status="pending"
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    
    # 2. Admin Auth
    su_email = "admin_verifier@test.com"
    su_headers = get_auth_headers(client, email=su_email)
    su_user = session.exec(select(User).where(User.email == su_email)).first()
    su_user.is_superuser = True
    session.add(su_user)
    session.commit()
    
    # 3. Approve
    resp = client.post(
        f"/api/v1/admin/kyc/{user.id}/verify",
        headers=su_headers,
        json={"decision": "approved", "notes": "Looks good"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # 4. Verify DB updates
    session.refresh(user)
    session.refresh(doc)
    assert user.kyc_status == "approved"
    assert doc.status == "verified"
