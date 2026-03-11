import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.user import User
from app.models.session import UserSession

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='2231896905', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_data(session):
    # Perms
    p1 = Permission(slug="p1:read", module="m1", action="read")
    p2 = Permission(slug="p1:write", module="m1", action="write")
    p3 = Permission(slug="p2:read", module="m2", action="read")
    session.add(p1)
    session.add(p2)
    session.add(p3)
    session.commit()
    
    # Role
    role = Role(name="Assign Test Role", is_active=True)
    session.add(role)
    session.commit()
    
    return role, p1, p2, p3

def test_assign_permissions_overwrite(client: TestClient, session: Session):
    admin = create_superuser(session)
    role, p1, p2, p3 = setup_data(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Assign p1
    session.add(RolePermission(role_id=role.id, permission_id=p1.id))
    session.commit()
    
    # Overwrite with p2, p3
    payload = {
        "permissions": ["p1:write", "p2:read"],
        "mode": "overwrite"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/roles/{role.id}/permissions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data["active_permissions"]) == 2
    assert "p1:write" in data["active_permissions"]
    assert "p2:read" in data["active_permissions"]
    assert "p1:read" not in data["active_permissions"]

def test_assign_permissions_append(client: TestClient, session: Session):
    admin = create_superuser(session)
    # Clean setup
    pA = Permission(slug="A", module="x", action="x")
    pB = Permission(slug="B", module="x", action="x")
    session.add(pA)
    session.add(pB)
    
    role = Role(name="Append Role", is_active=True)
    session.add(role)
    session.commit()
    
    # Start with A
    session.add(RolePermission(role_id=role.id, permission_id=pA.id))
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Append B
    payload = {
        "permissions": ["B"],
        "mode": "append"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/roles/{role.id}/permissions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data["active_permissions"]) == 2
    assert "A" in data["active_permissions"]
    assert "B" in data["active_permissions"]

def test_assign_invalid_slug(client: TestClient, session: Session):
    admin = create_superuser(session)
    role = Role(name="Invalid Test", is_active=True)
    session.add(role)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {
        "permissions": ["fake:slug"],
        "mode": "overwrite"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/roles/{role.id}/permissions", json=payload)
    assert resp.status_code == 400
    assert "Invalid permission slugs" in resp.json()["detail"]

def test_assign_permissions_invalidates_sessions(client: TestClient, session: Session):
    admin = create_superuser(session)
    role = Role(name="Session Role", is_active=True)
    session.add(role)
    session.commit()
    
    # Create User assigned to Role
    user = User(phone_number='3049981769', email="u@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    session.add(UserRole(user_id=user.id, role_id=role.id))
    
    # Create Active Session
    user_session = UserSession(user_id=user.id, token_id="abc", is_active=True)
    session.add(user_session)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Assign Perms -> Should trigger invalidation
    p = Permission(slug="p:sess", module="x", action="x")
    session.add(p)
    session.commit()
    
    payload = {
        "permissions": ["p:sess"],
        "mode": "overwrite"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/roles/{role.id}/permissions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["users_affected"] == 1
    
    # Verify DB
    session.refresh(user_session)
    assert user_session.is_active is False
