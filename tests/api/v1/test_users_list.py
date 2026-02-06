import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.rbac import Role
from app.models.address import Address
from app.models.rbac import UserRole
import time
from datetime import datetime, timedelta

def create_user(session, email, name, last_login_offset=0):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(
            email=email,
            full_name=name,
            phone_number=f"999{hash(email) % 10000000}",
            hashed_password="hashed_password",
            is_active=True,
            kyc_status="verified",
            last_login=datetime.utcnow() - timedelta(minutes=last_login_offset) if last_login_offset >= 0 else None
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user

def test_list_users_sorting(client: TestClient, session: Session):
    # Setup users with different last_login
    # User A: Login now (most recent)
    # User B: Login 10 mins ago
    # User C: Login 20 mins ago
    
    user_a = create_user(session, "a@listTest.com", "User A", 0)
    user_b = create_user(session, "b@listTest.com", "User B", 10)
    user_c = create_user(session, "c@listTest.com", "User C", 20)
    
    # Make User A admin for the request
    role_admin = session.exec(select(Role).where(Role.name == "super_admin")).first()
    if not role_admin:
        role_admin = Role(name="super_admin")
        session.add(role_admin)
        session.commit()
        session.refresh(role_admin)
    
    if not session.exec(select(UserRole).where(UserRole.user_id==user_a.id, UserRole.role_id==role_admin.id)).first():
        session.add(UserRole(user_id=user_a.id, role_id=role_admin.id))
        session.commit()

    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user_a
    
    # 1. Sort by last_login DESC (default expectation: A, B, C)
    resp = client.get("/api/v1/users/?sort_by=last_login&sort_order=desc&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    users = data["users"]
    
    # Filter our test users
    test_emails = ["a@listTest.com", "b@listTest.com", "c@listTest.com"]
    found_users = [u for u in users if u["email"] in test_emails]
    
    # Must find at least our 3 users
    assert len(found_users) == 3
    # Verify order
    assert found_users[0]["email"] == "a@listTest.com"
    assert found_users[1]["email"] == "b@listTest.com"
    assert found_users[2]["email"] == "c@listTest.com"

    # 2. Sort by last_login ASC (C, B, A)
    resp = client.get("/api/v1/users/?sort_by=last_login&sort_order=asc&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    users = data["users"]
    found_users = [u for u in users if u["email"] in test_emails]
    
    assert found_users[0]["email"] == "c@listTest.com"
    assert found_users[1]["email"] == "b@listTest.com"
    assert found_users[2]["email"] == "a@listTest.com"

def test_login_updates_timestamp(client: TestClient, session: Session):
    # Create user
    email = "login_ts@test.com"
    password = "Password123!"
    user = create_user(session, email, "Login TS User")
    
    # Manually set hashed password and clear last_login
    from app.core.security import get_password_hash
    user.hashed_password = get_password_hash(password)
    user.last_login = None
    session.add(user)
    session.commit()
    session.refresh(user)
    
    assert user.last_login is None
    
    # Use real authentication flow
    # Need to remove override for this test or partially mock?
    # Actually, we can just call the endpoint. But 'client' needs override for other tests.
    # We can use a fresh dependency override context logic or cleared override.
    
    
    # app = client.app
    # app.dependency_overrides = {} # Do not clear! client fixture handles DB override.
    
    # Assign role
    role = session.exec(select(Role).where(Role.name == "customer")).first()
    if not role:
        role = Role(name="customer")
        session.add(role)
        session.commit()
    
    if not session.exec(select(UserRole).where(UserRole.user_id==user.id, UserRole.role_id==role.id)).first():
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()

    resp = client.post("/api/v1/auth/login", json={"username": email, "password": password})
    assert resp.status_code == 200
    
    session.refresh(user)
    assert user.last_login is not None
