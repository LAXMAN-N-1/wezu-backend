
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.core.config import settings
from app.api import deps
from app.models.user import User





def test_list_sessions(client: TestClient, session: Session):
    # 1. Create User
    from app.core.security import get_password_hash
    user = User(
        email="session_test@example.com", 
        hashed_password=get_password_hash("password"),
        is_active=True,
        full_name="Session Tester",
        phone_number="1234567890"
    )
    session.add(user)
    session.commit()
    
    # 2. Login (Creates Session)
    login_data = {
        "username": "session_test@example.com",
        "password": "password"
    }
    # Simulate device header
    headers = {"X-Device-ID": "device-123", "User-Agent": "TestClient/1.0"}
    r = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data, headers=headers)
    assert r.status_code == 200, f"Login failed: {r.text}"
    tokens = r.json()
    access_token = tokens["access_token"]
    
    # 3. List Sessions
    r = client.get(
        f"{settings.API_V1_STR}/sessions/list",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) >= 1
    assert sessions[0]["device_type"] == "TestClient/1.0" or "unknown" # Depends on UA parser
    assert sessions[0]["is_active"] == True
    assert sessions[0]["is_current"] == True, "Session should be marked as current"

def test_revoke_session(client: TestClient, session: Session):
    # 1. Create User
    from app.core.security import get_password_hash
    user = User(
        email="revoke_test@example.com", 
        hashed_password=get_password_hash("password"),
        is_active=True,
        full_name="Revoke Tester",
        phone_number="0987654321"
    )
    session.add(user)
    session.commit()
    
    # 2. Login twice (2 sessions)
    login_data = {"username": "revoke_test@example.com", "password": "password"}
    
    # Session 1
    r1 = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data, headers={"X-Device-ID": "dev1"})
    assert r1.status_code == 200
    token1 = r1.json()["access_token"]
    
    # Session 2
    r2 = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data, headers={"X-Device-ID": "dev2"})
    assert r2.status_code == 200
    token2 = r2.json()["access_token"]
    
    # 3. List
    r = client.get(f"{settings.API_V1_STR}/sessions/list", headers={"Authorization": f"Bearer {token1}"})
    sessions = r.json()
    assert len(sessions) >= 2
    
    session_id_to_revoke = sessions[0]["id"]
    
    # 4. Revoke Session 1 using Token 1 (Self revocation)
    r = client.post(
        f"{settings.API_V1_STR}/sessions/revoke/{session_id_to_revoke}",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert r.status_code == 200
    
    # 5. Verify it's inactive
    from app.models.session import UserSession
    db_session = session.get(UserSession, session_id_to_revoke)
    assert db_session.is_active == False
