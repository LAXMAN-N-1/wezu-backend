import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission
from datetime import datetime

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='2310138661', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def seed_permissions(session):
    perms = [
        Permission(slug="test:read", module="test", action="read"),
        Permission(slug="test:write", module="test", action="write"),
        Permission(slug="other:read", module="other", action="read")
    ]
    for p in perms:
        if not session.exec(select(Permission).where(Permission.slug == p.slug)).first():
            session.add(p)
    session.commit()

def test_create_role(client: TestClient, session: Session):
    admin = create_superuser(session)
    seed_permissions(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {
        "name": "Test Role",
        "category": "vendor_staff",
        "level": 10,
        "permissions": ["test:read"]
    }
    
    resp = client.post("/api/v1/admin/rbac/roles", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Role"
    assert data["category"] == "vendor_staff"
    assert data["level"] == 10
    
    # Check permission
    role_perms = session.exec(select(Permission).join(RolePermission).where(RolePermission.role_id == data["id"])).all()
    assert len(role_perms) == 1
    assert role_perms[0].slug == "test:read"

def test_role_uniqueness(client: TestClient, session: Session):
    admin = create_superuser(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {"name": "Unique Role", "category": "system", "permissions": []}
    # First creation - should succeed
    resp = client.post("/api/v1/admin/rbac/roles", json=payload)
    assert resp.status_code == 200
    
    # Second creation - should fail
    resp = client.post("/api/v1/admin/rbac/roles", json=payload)
    assert resp.status_code == 400

def test_role_inheritance(client: TestClient, session: Session):
    admin = create_superuser(session)
    seed_permissions(session)
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Create Parent
    parent_payload = {
        "name": "Parent Role",
        "category": "system",
        "permissions": ["test:read", "test:write"]
    }
    resp = client.post("/api/v1/admin/rbac/roles", json=parent_payload)
    assert resp.status_code == 200
    parent_id = resp.json()["id"]
    
    # Create Child with inheritance
    child_payload = {
        "name": "Child Role",
        "category": "system",
        "parent_role_id": parent_id,
        "permissions": ["other:read"] # Should have this + parent perms
    }
    resp = client.post("/api/v1/admin/rbac/roles", json=child_payload)
    assert resp.status_code == 200
    child_data = resp.json()
    
    # Verify Permissions
    # Should have: test:read, test:write (from parent) AND other:read (own)
    child_role = session.get(Role, child_data["id"])
    assert child_role.parent_role_id == parent_id
    
    perms = session.exec(select(Permission.slug).join(RolePermission).where(RolePermission.role_id == child_role.id)).all()
    assert "test:read" in perms
    assert "test:write" in perms
    assert "other:read" in perms
    assert len(perms) == 3
