import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.user import User
from app.models.video_kyc import VideoKYCSession
from app.core.config import settings

# --- Helper Functions (Duplicated to avoid import issues) ---
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

def test_video_kyc_flow(
    client: TestClient, session: Session
) -> None:
    # 1. Setup: User
    email = "video_kyc_user@test.com"
    user_headers = get_auth_headers(client, email=email)
    
    # Set pending
    user = session.exec(select(User).where(User.email == email)).first()
    user.kyc_status = "pending_verification"
    session.add(user)
    session.commit()
    
    # 2. User Requests Video KYC
    req_response = client.post(
        f"{settings.API_V1_STR}/me/kyc/video-kyc/request",
        headers=user_headers
    )
    assert req_response.status_code == 200
    session_data = req_response.json()
    assert session_data["status"] == "scheduled" # or initiated
    session_id = session_data["id"]
    
    # Verify DB
    vks = session.get(VideoKYCSession, session_id)
    assert vks is not None
    assert vks.user_id is not None

    # 3. Setup: Admin User
    admin_headers = get_auth_headers(client, email="admin_video@test.com")
    admin_user = session.exec(select(User).where(User.email == "admin_video@test.com")).first()
    admin_user.is_superuser = True
    session.add(admin_user)
    session.commit()

    # 4. Admin Completes Session (Approved)
    complete_data = {
        "verification_result": "approved",
        "recording_link": "http://s3.com/video.mp4",
        "agent_notes": "User looks legitimate."
    }
    
    complete_response = client.post(
        f"{settings.API_V1_STR}/admin/kyc/video-kyc/{session_id}/complete",
        headers=admin_headers,
        json=complete_data
    )
    
    assert complete_response.status_code == 200
    assert complete_response.json()["session_status"] == "completed"
    
    # 5. Verify DB Updates
    session.refresh(vks)
    assert vks.status == "completed"
    assert vks.video_url == "http://s3.com/video.mp4"
    assert vks.agent_notes == "User looks legitimate."
    
    # Verify User Status Updated
    user = session.exec(select(User).where(User.email == email)).first()
    assert user.kyc_status == "verified"

def test_video_kyc_rejection(
    client: TestClient, session: Session
) -> None:
    # 1. Setup: User & Request
    email = "video_reject@test.com"
    user_headers = get_auth_headers(client, email=email)
    
    # Set pending
    user = session.exec(select(User).where(User.email == email)).first()
    user.kyc_status = "pending_verification"
    session.add(user)
    session.commit()

    req_response = client.post(
         f"{settings.API_V1_STR}/me/kyc/video-kyc/request",
        headers=user_headers
    )
    session_id = req_response.json()["id"]
    
    # 2. Admin Auth
    admin_headers = get_auth_headers(client, email="admin_video_2@test.com")
    admin_user = session.exec(select(User).where(User.email == "admin_video_2@test.com")).first()
    admin_user.is_superuser = True
    session.add(admin_user)
    session.commit()
    
    # 3. Admin Rejects
    complete_data = {
        "verification_result": "rejected",
        "agent_notes": "User did not show face."
    }
    
    client.post(
        f"{settings.API_V1_STR}/admin/kyc/video-kyc/{session_id}/complete",
        headers=admin_headers,
        json=complete_data
    )
    
    # 4. Verify
    vks = session.get(VideoKYCSession, session_id)
    assert vks.status == "rejected"
    
    # User status should NOT auto-verify
    user = session.exec(select(User).where(User.email == email)).first()
    assert user.kyc_status != "verified"
