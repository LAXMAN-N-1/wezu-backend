import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.user import User
from app.models.session import UserSession
from datetime import datetime, UTC, timedelta

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='3223004283', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_role_and_user(session):
    # Role
    role = Role(name="Editable Role", category="system", level=10, description="Old Desc")
    session.add(role)
    session.commit()
    
    # Permission
    p1 = Permission(slug="p1", module="m", action="a")
    p2 = Permission(slug="p2", module="m", action="b")
    session.add(p1)
    session.add(p2)
    session.commit()
    session.add(RolePermission(role_id=role.id, permission_id=p1.id))
    
    # User & Session
    user = User(phone_number='2763621620', email="u@test.com", hashed_password="pw")
    session.add(user)
    session.commit()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    
    us = UserSession(user_id=user.id, token_id="t1", expires_at=datetime.now(UTC) + timedelta(hours=1), ip_address="1.1.1.1")
    session.add(us)
    session.commit()
    session.refresh(us)
    
    return role, user, us

def test_update_role_metadata(client: TestClient, session: Session):
    admin = create_superuser(session)
    role, _, _ = setup_role_and_user(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    payload = {
        "description": "New Desc",
        "level": 20
    }
    resp = client.put(f"/api/v1/admin/rbac/roles/{role.id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "New Desc"
    assert data["level"] == 20

def test_update_role_permissions_and_invalidation(client: TestClient, session: Session):
    admin = create_superuser(session)
    role, user, us = setup_role_and_user(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    assert us.is_active is True
    
    # Update perms -> Shoudl trigger session invalidation
    payload = {
        "permissions": ["p2"] # Switch from p1 to p2
    }
    resp = client.put(f"/api/v1/admin/rbac/roles/{role.id}", json=payload)
    assert resp.status_code == 200
    
    # Check permissions
    role_perms = session.exec(select(Permission.slug).join(RolePermission).where(RolePermission.role_id == role.id)).all()
    assert "p2" in role_perms
    assert "p1" not in role_perms
    
    # Check session
    session.refresh(us)
    assert us.is_active is False

def test_update_system_role_protection(client: TestClient, session: Session):
    admin = create_superuser(session)
    role, _, _ = setup_role_and_user(session)
    
    # Mark as system role
    role.is_system_role = True
    session.add(role)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Try rename
    payload = {"name": "New Name"}
    resp = client.put(f"/api/v1/admin/rbac/roles/{role.id}", json=payload)
    assert resp.status_code == 400
