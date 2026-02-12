import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role
from app.core.config import settings
from fastapi.testclient import TestClient

def get_auth_headers(client: TestClient, email: str = "auth_audit_admin@test.com", role: str = "admin"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Auth Audit Admin",
            "phone_number": str(abs(hash(email)))[:10].ljust(10, '0')
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

def test_auth_failure_audit_flow(client, session: Session):
    # 1. Setup Admin
    email = "auth_audit_admin@test.com"
    headers = get_auth_headers(client, email=email)
    
    # Ensure admin role and superuser
    user = session.exec(select(User).where(User.email == email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    # Assign role safely
    from app.models.rbac import UserRole
    from sqlalchemy.exc import IntegrityError
    
    link = UserRole(user_id=user.id, role_id=admin_role.id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # 2. Trigger Failed Login (Wrong Password)
    # Using User ID detection logic: "test_auth_audit_user@example.com"
    target_email = "target_auth_fail@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": target_email,
            "password": "CorrectPassword123!",
            "full_name": "Target User",
            "phone_number": "9999999999"
        },
    )
    
    # Get ID
    target_user = session.exec(select(User).where(User.email == target_email)).first()
    assert target_user is not None
    
    # Fail Login
    resp = client.post(
        "/api/v1/auth/token",
        data={
            "username": target_email,
            "password": "WRONG_PASSWORD"
        },
    )
    assert resp.status_code == 400
    
    # 3. Trigger Failed Login (Non-existent User) - Optional validation depending on implementation
    # Note: Our implementation logs "User not found" too in `login` endpoint, 
    # but `login_access_token` raises 400 for generic "Incorrect email or password" if user not found.
    # Let's test the `login` endpoint (JSON) for clear differentiation if we implemented it there.
    # We implemented logging in `login_access_token` inside the check: `if not user or not verify...`
    # If user is None, it logs with user_id=None.
    
    non_existent_email = "ghost@example.com"
    resp = client.post(
        "/api/v1/auth/token",
        data={
            "username": non_existent_email,
            "password": "password"
        },
    )
    assert resp.status_code == 400
    
    # 4. Fetch Audit Logs
    resp = client.get(f"{settings.API_V1_STR}/audit/auth/failures", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    logs = data["logs"]
    
    # Verify Failure 1 (Wrong Password)
    fail1 = next((l for l in logs if l["resource_id"] == str(target_user.id) and l["action"] == "login_failed"), None)
    assert fail1 is not None
    assert "Incorrect" in fail1["details"]
    
    # Verify Failure 2 (Non-existent)
    # resource_id should be "ghost@example.com" as we set it to username if user not found
    fail2 = next((l for l in logs if l["resource_id"] == non_existent_email and l["action"] == "login_failed"), None)
    assert fail2 is not None
