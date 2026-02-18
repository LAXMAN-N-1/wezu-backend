
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.core.config import settings
from app.models.user import User
from app.models.session import UserSession

def test_admin_force_logout(client: TestClient, session: Session):
    # 1. Create Admin & Target User
    from app.core.security import get_password_hash
    
    admin = User(
        email="admin_test@example.com", 
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
        full_name="Admin Tester",
        phone_number="1111111111"
    )
    session.add(admin)
    
    target = User(
        email="target_test@example.com", 
        hashed_password=get_password_hash("password"),
        is_active=True,
        full_name="Target User",
        phone_number="2222222222"
    )
    session.add(target)
    session.commit()
    
    # 2. Login as Target (Create Session)
    r = client.post(
        f"{settings.API_V1_STR}/auth/login", 
        data={"username": "target_test@example.com", "password": "password"}
    )
    assert r.status_code == 200, f"Target login failed: {r.text}"
    
    # Verify session exists
    user_session = session.exec(select(UserSession).where(UserSession.user_id == target.id)).first()
    assert user_session.is_active == True
    
    # 3. Login as Admin
    r_admin = client.post(
        f"{settings.API_V1_STR}/auth/login", 
        data={"username": "admin_test@example.com", "password": "password"}
    )
    assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
    admin_token = r_admin.json()["access_token"]
    
    # 4. Force Logout
    r = client.post(
        f"{settings.API_V1_STR}/admin/users/{target.id}/force-logout",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 200
    
    # 5. Verify Session Inactive
    session.refresh(user_session)
    assert user_session.is_active == False

def test_admin_ban_user(client: TestClient, session: Session):
    # 1. Setup (reuse logic or create new)
    from app.core.security import get_password_hash
    admin = User(
        email="admin_ban@example.com", 
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
        full_name="Admin Banner",
        phone_number="3333333333"
    )
    session.add(admin)
    
    victim = User(
        email="victim@example.com", 
        hashed_password=get_password_hash("password"),
        is_active=True,
        full_name="Victim",
        phone_number="4444444444"
    )
    session.add(victim)
    session.commit()
    
    # Login Victim
    r = client.post(
        f"{settings.API_V1_STR}/auth/login", 
        data={"username": "victim@example.com", "password": "password"}
    )
    assert r.status_code == 200
    
    # Login Admin
    r_admin = client.post(
        f"{settings.API_V1_STR}/auth/login", 
        data={"username": "admin_ban@example.com", "password": "password"}
    )
    assert r_admin.status_code == 200
    admin_token = r_admin.json()["access_token"]
    
    # 2. Ban User
    r = client.post(
        f"{settings.API_V1_STR}/admin/users/{victim.id}/ban",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"reason": "Spam"}
    )
    assert r.status_code == 200
    
    # 3. Verify
    session.refresh(victim)
    assert victim.is_active == False
    
    # Verify sessions revoked
    sessions = session.exec(select(UserSession).where(UserSession.user_id == victim.id)).all()
    for s in sessions:
        assert s.is_active == False
