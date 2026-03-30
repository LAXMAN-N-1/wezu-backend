import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, UserRole
from app.models.user import User

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='9528790507', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_delete_role_lifecycle(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # 1. Create Role
    role = Role(name="Temp Role", is_active=True)
    session.add(role)
    session.commit()
    session.refresh(role)
    
    # Verify it shows up in list
    resp = client.get("/api/v1/admin/rbac/roles?active_only=true")
    assert any(r["id"] == role.id for r in resp.json())
    
    # 2. Delete Role
    resp = client.delete(f"/api/v1/admin/rbac/roles/{role.id}")
    assert resp.status_code == 200
    
    # 3. Verify it's gone from active list
    resp = client.get("/api/v1/admin/rbac/roles?active_only=true")
    assert not any(r["id"] == role.id for r in resp.json())
    
    # 4. Verify it's still in DB as inactive
    session.refresh(role)
    assert role.is_active is False

def test_delete_role_prevention_active_users(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Role with User
    role = Role(name="Busy Role", is_active=True)
    session.add(role)
    session.commit()
    
    user = User(phone_number='8207630572', email="test@u.com", hashed_password="pw")
    session.add(user)
    session.commit()
    
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.commit()
    
    # Try Delete
    resp = client.delete(f"/api/v1/admin/rbac/roles/{role.id}")
    assert resp.status_code == 400
    assert "active users" in resp.json()["error"]

def test_delete_system_role_prevention(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    role = Role(name="Core Sys", is_active=True, is_system_role=True)
    session.add(role)
    session.commit()
    
    resp = client.delete(f"/api/v1/admin/rbac/roles/{role.id}")
    assert resp.status_code == 400
    assert "system roles" in resp.json()["error"]
