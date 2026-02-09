import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.user import User
from app.models.kyc import KYCDocument
from app.core.config import settings

# --- Helper Functions ---
def random_lower_string(length: int = 10, chars: str = string.ascii_lowercase) -> str:
    return "".join(random.choice(chars) for _ in range(length))

def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"

def get_auth_headers(client: TestClient, email: str = None) -> dict:
    if not email:
        email = random_email()
    password = "Password123!"
    phone = f"+91{random.randint(1000000000, 9999999999)}"
    
    # Register
    client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "phone_number": phone
        },
    )
    
    # Login
    response = client.post(
        f"{settings.API_V1_STR}/auth/token",
        data={
            "username": email,
            "password": password
        },
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

# --- Tests ---

def test_kyc_rejection_and_resubmission_flow(
    client: TestClient, session: Session
) -> None:
    # 1. Setup: User with pending KYC
    email = "rejected_user@test.com"
    user_headers = get_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.kyc_status = "pending_verification"
    session.add(user)
    session.commit()
    session.refresh(user)

    # 2. Setup: Admin User
    admin_headers = get_auth_headers(client, email="admin_rejector@test.com")
    admin_user = session.exec(select(User).where(User.email == "admin_rejector@test.com")).first()
    admin_user.is_superuser = True
    session.add(admin_user)
    session.commit()

    # 3. Admin Rejects User
    reject_data = {
        "reason": "Documents are blurry",
        "rejection_reasons": {}
    }
    
    response = client.post(
        f"{settings.API_V1_STR}/admin/kyc/{user.id}/reject",
        headers=admin_headers,
        json=reject_data,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_status"] == "rejected"
    assert data["reason"] == "Documents are blurry"
    
    # Verify DB state
    session.refresh(user)
    assert user.kyc_status == "rejected"
    assert user.kyc_rejection_reason == "Documents are blurry"
    
    # 4. User Checks Status
    status_response = client.get(
        f"{settings.API_V1_STR}/me/kyc",
        headers=user_headers
    )
    assert status_response.status_code == 200
    assert status_response.json()["kyc_status"] == "rejected"
    assert status_response.json()["rejection_reason"] == "Documents are blurry"
    
    # 5. User Resubmits
    resubmit_response = client.post(
        f"{settings.API_V1_STR}/me/kyc/resubmit",
        headers=user_headers
    )
    
    assert resubmit_response.status_code == 200
    res_data = resubmit_response.json()
    assert res_data["kyc_status"] == "pending_verification"
    
    # Verify DB State
    session.refresh(user)
    assert user.kyc_status == "pending_verification"
    assert user.kyc_rejection_reason is None

def test_invalid_resubmission_when_verified(
    client: TestClient, session: Session
) -> None:
    # Setup: Verified User
    email = "verified_user@test.com"
    user_headers = get_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.kyc_status = "verified"
    session.add(user)
    session.commit()
    
    # Try to resubmit
    response = client.post(
        f"{settings.API_V1_STR}/me/kyc/resubmit",
        headers=user_headers
    )
    
    assert response.status_code == 400
    assert "Can only resubmit" in response.json()["detail"]
