import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@check.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='1170189352', 
        email="admin@check.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_user_and_roles(session):
    # Permissions
    p_direct = Permission(slug="direct:action", module="m", action="a")
    p_inherited = Permission(slug="inherited:action", module="m", action="b", scope="region")
    session.add(p_direct)
    session.add(p_inherited)
    session.commit()
    
    # Roles
    parent_role = Role(name="Parent Role", is_active=True)
    session.add(parent_role)
    session.commit()
    # Add inherited perm to parent (properly)
    # Re-fetch or append
    parent_role.permissions.append(p_inherited)
    session.add(parent_role)
    session.commit()
    
    child_role = Role(name="Child Role", is_active=True, parent_role_id=parent_role.id)
    child_role.permissions.append(p_direct)
    session.add(child_role)
    session.commit()
    
    # User
    user = User(phone_number='2668259408', email="checker@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    # Assign Child Role to User
    session.add(UserRole(user_id=user.id, role_id=child_role.id))
    session.commit()
    
    return user, child_role, parent_role

def test_check_permission_direct(client: TestClient, session: Session):
    admin = create_superuser(session)
    user, child, parent = setup_user_and_roles(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Check direct permission
    resp = client.get(
        f"/api/v1/admin/rbac/users/{user.id}/permissions/check",
        params={"permission": "direct:action"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_permission"] is True
    assert data["granted_by_role"] == "Child Role"
    assert data["scope"] == "all" # default

def test_check_permission_inherited(client: TestClient, session: Session):
    admin = create_superuser(session)
    user, child, parent = setup_user_and_roles(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Check inherited permission
    resp = client.get(
        f"/api/v1/admin/rbac/users/{user.id}/permissions/check",
        params={"permission": "inherited:action"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_permission"] is True
    # Implementation returns the User's role that provided access
    # Even if it came from parent, the 'entry point' is Child Role
    assert data["granted_by_role"] == "Child Role" 
    assert data["scope"] == "region"

def test_check_permission_negative(client: TestClient, session: Session):
    admin = create_superuser(session)
    user, child, parent = setup_user_and_roles(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get(
        f"/api/v1/admin/rbac/users/{user.id}/permissions/check",
        params={"permission": "non:existent"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_permission"] is False
    assert data["granted_by_role"] is None

def test_check_permission_user_not_found(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get(
        "/api/v1/admin/rbac/users/99999/permissions/check",
        params={"permission": "any"}
    )
    
    assert resp.status_code == 404
