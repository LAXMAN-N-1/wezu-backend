import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.user import User

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='2968035923', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_role_hierarchy(session):
    # Top Role
    top_role = Role(name="Top Role", category="system", level=100)
    session.add(top_role)
    session.commit()
    
    # Permission
    perm = Permission(slug="top:read", module="top", action="read")
    session.add(perm)
    session.commit()
    session.add(RolePermission(role_id=top_role.id, permission_id=perm.id))
    
    # Child Role
    child_role = Role(name="Child Role", category="system", level=50, parent_role_id=top_role.id)
    session.add(child_role)
    session.commit()
    
    # User for Child Role
    user = User(phone_number='5260496081', email="user@test.com", hashed_password="pw")
    session.add(user)
    session.commit()
    session.add(UserRole(user_id=user.id, role_id=child_role.id))
    session.commit()
    
    return top_role, child_role

def test_get_role_detail_structure(client: TestClient, session: Session):
    admin = create_superuser(session)
    top_role, child_role = setup_role_hierarchy(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Test Top Role
    resp = client.get(f"/api/v1/admin/rbac/roles/{top_role.id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["name"] == "Top Role"
    assert "permission_tree" in data
    assert data["permission_tree"]["top"] == ["read"]
    assert len(data["child_roles"]) == 1
    assert data["child_roles"][0]["name"] == "Child Role"

def test_get_role_detail_user_count(client: TestClient, session: Session):
    admin = create_superuser(session)
    top_role, child_role = setup_role_hierarchy(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Test Child Role
    resp = client.get(f"/api/v1/admin/rbac/roles/{child_role.id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["user_count"] == 1
    assert data["parent_role"]["name"] == "Top Role"

def test_get_role_detail_not_found(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    resp = client.get("/api/v1/admin/rbac/roles/999999")
    assert resp.status_code == 404
