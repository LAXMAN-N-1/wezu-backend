import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.audit_log import AuditLog
from app.core.config import settings
from fastapi.testclient import TestClient

def get_auth_headers(client: TestClient, email: str = "audit_user@test.com", role: str = None):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Audit User",
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
    if not token and role == "admin": 
        # If admin login failed (maybe need to set is_superuser manually in DB for test), 
        # we might need to handle it. 
        # But for this test, we rely on register+login working for standard user.
        # For admin specific tests, we usually use a fixture or modify DB.
        pass
        
    return {"Authorization": f"Bearer {token}"}

def test_audit_log_flow(client, session: Session):
    # 1. Setup: User and Admin
    user_email = "audit_user@test.com"
    user_headers = get_auth_headers(client, email=user_email)
    
    admin_email = "audit_admin@test.com"
    admin_headers = get_auth_headers(client, email=admin_email, role="admin") # Assuming get_auth_headers handles role creation/assignment if needed, or we rely on default user creation
    
    # Get user IDs
    user = session.exec(select(User).where(User.email == user_email)).first()
    
    # Assign Admin Role to admin user
    from app.models.rbac import Role
    admin_user = session.exec(select(User).where(User.email == admin_email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    # Ensure admin role exists (it should from init_db, but for safety in tests)
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
        session.refresh(admin_role)
    
    # Check if role already assigned using direct query to avoid loading issues
    from app.models.rbac import UserRole
    existing_link = session.exec(
        select(UserRole).where(
            UserRole.user_id == admin_user.id,
            UserRole.role_id == admin_role.id
        )
    ).first()
    
    # Assign role safely
    from app.models.rbac import UserRole
    from sqlalchemy.exc import IntegrityError
    
    link = UserRole(user_id=admin_user.id, role_id=admin_role.id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        
    session.refresh(admin_user)
        
    admin = admin_user
    
    # 2. Trigger Login (which should log action)
    # The get_auth_headers helper might strictly generate tokens without hitting the login endpoint if it uses internal helpers. 
    # Let's manually hit the login endpoint to ensure the audit log is created.
    
    login_data = {
        "username": user_email,
        "password": "password" # Assuming default password from helper
    }
    client.post(f"{settings.API_V1_STR}/auth/login", json=login_data)
    
    # Verify Audit Log entry exists
    log_statement = select(AuditLog).where(AuditLog.user_id == user.id)
    logs = session.exec(log_statement).all()
    assert len(logs) >= 1
    assert logs[0].action == "login"
    
    # 3. Test GET /audit/users/{user_id} as User (Self)
    response = client.get(
        f"{settings.API_V1_STR}/audit/users/{user.id}",
        headers=user_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) >= 1
    assert data["logs"][0]["action"] == "login"
    
    # 4. Test GET /audit/users/{user_id} as Admin
    response_admin = client.get(
        f"{settings.API_V1_STR}/audit/users/{user.id}",
        headers=admin_headers
    )
    assert response_admin.status_code == 200
    assert len(response_admin.json()["logs"]) >= 1
    
    # 5. Test Forbidden access (User A trying to see User B)
    other_user_email = "other_audit@test.com"
    other_headers = get_auth_headers(client, email=other_user_email)
    
    response_forbidden = client.get(
        f"{settings.API_V1_STR}/audit/users/{user.id}",
        headers=other_headers
    )
    assert response_forbidden.status_code == 403
