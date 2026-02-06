import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_source_role(session):
    role = Role(name="Source Role", category="system", level=10, description="Original")
    session.add(role)
    session.commit()
    
    p1 = Permission(slug="dup:p1", module="dup", action="read")
    session.add(p1)
    session.commit()
    session.add(RolePermission(role_id=role.id, permission_id=p1.id))
    session.commit()
    
    return role, p1

def test_duplicate_role_success(client: TestClient, session: Session):
    admin = create_superuser(session)
    source_role, p1 = setup_source_role(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {
        "new_name": "Cloned Role",
        "description": "Cloned Description"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/roles/{source_role.id}/duplicate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["name"] == "Cloned Role"
    assert data["description"] == "Cloned Description"
    assert data["parent_role_id"] == source_role.parent_role_id
    assert data["category"] == source_role.category
    assert data["is_system_role"] is False
    
    # Check permissions logic
    # Note: permissions field in response might be None depending on active endpoint config, so check DB
    new_role_id = data["id"]
    new_perms = session.exec(select(Permission.slug).join(RolePermission).where(RolePermission.role_id == new_role_id)).all()
    assert "dup:p1" in new_perms

def test_duplicate_role_name_conflict(client: TestClient, session: Session):
    admin = create_superuser(session)
    source_role, _ = setup_source_role(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Try to duplicate with same name as source (which exists)
    payload = {"new_name": "Source Role"}
    resp = client.post(f"/api/v1/admin/rbac/roles/{source_role.id}/duplicate", json=payload)
    assert resp.status_code == 400
