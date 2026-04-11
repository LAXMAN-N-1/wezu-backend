import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@list.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='3146685163', 
        email="admin@list.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_complex_roles(session):
    # Perms
    p1 = Permission(slug="m1:read", module="m1", action="read")
    p2 = Permission(slug="m1:write", module="m1", action="write")
    p3 = Permission(slug="m2:read", module="m2", action="read")
    session.add(p1)
    session.add(p2)
    session.add(p3)
    session.commit()
    
    # Role A has p1
    role_a = Role(name="Role A", is_active=True)
    session.add(role_a)
    session.commit()
    role_a.permissions.append(p1)
    
    # Role B has p3
    role_b = Role(name="Role B", is_active=True)
    session.add(role_b)
    session.commit()
    role_b.permissions.append(p3)
    
    # Role C inherits from A and adds p2
    role_c = Role(name="Role C", is_active=True, parent_role_id=role_a.id)
    session.add(role_c)
    session.commit()
    role_c.permissions.append(p2)
    
    session.add(role_c) # Re-add to ensure relationship
    session.commit()
    
    return role_a, role_b, role_c

def test_get_user_permissions_multiple_roles(client: TestClient, session: Session):
    admin = create_superuser(session)
    role_a, role_b, role_c = setup_complex_roles(session)
    
    user = User(phone_number='2482454013', email="multi@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    # Assign Role B and Role C
    # Expected: 
    # From Role B -> m2:read
    # From Role C -> m1:write
    # From Role C (via A) -> m1:read
    
    session.add(UserRole(user_id=user.id, role_id=role_b.id))
    session.add(UserRole(user_id=user.id, role_id=role_c.id))
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get(f"/api/v1/admin/rbac/users/{user.id}/permissions")
    assert resp.status_code == 200
    data = resp.json()
    
    modules = {m["module"]: m for m in data["modules"]}
    
    assert "m1" in modules
    assert "m2" in modules
    
    # Check m1 permissions (should have read and write)
    m1_perms = {p["id"] for p in modules["m1"]["permissions"]}
    assert "m1:read" in m1_perms
    assert "m1:write" in m1_perms
    
    # Check m2 permissions
    m2_perms = {p["id"] for p in modules["m2"]["permissions"]}
    assert "m2:read" in m2_perms

def test_get_user_permissions_empty(client: TestClient, session: Session):
    admin = create_superuser(session)
    user = User(phone_number='5909566784', email="empty@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get(f"/api/v1/admin/rbac/users/{user.id}/permissions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["modules"]) == 0
