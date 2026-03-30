import uuid
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
    user = AdminUser(phone_number='3145227719', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def seed_roles(session):
    # Ensure standard roles exist or create them
    roles = [
        {"name": "Vendor Staff", "category": "vendor_staff", "level": 10},
        {"name": "Powerfill Staff", "category": "powerfill_staff", "level": 20},
        {"name": "System Admin", "category": "system", "level": 100},
    ]
    
    for r in roles:
        if not session.exec(select(Role).where(Role.name == r["name"])).first():
            role = Role(**r)
            session.add(role)
    session.commit()

def test_list_roles_all(client: TestClient, session: Session):
    admin = create_superuser(session)
    seed_roles(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get("/api/v1/admin/rbac/roles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    # Check structure
    assert "permission_count" in data[0]

def test_list_roles_filter_category(client: TestClient, session: Session):
    admin = create_superuser(session)
    seed_roles(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get("/api/v1/admin/rbac/roles?category=vendor_staff")
    assert resp.status_code == 200
    data = resp.json()
    
    for role in data:
        assert role["category"] == "vendor_staff"

def test_list_roles_exclude_permissions(client: TestClient, session: Session):
    admin = create_superuser(session)
    seed_roles(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Check default (include=True)
    resp = client.get("/api/v1/admin/rbac/roles")
    assert resp.json()[0]["permissions"] is not None
    
    # Check exclude
    resp = client.get("/api/v1/admin/rbac/roles?include_permissions=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["permissions"] is None
    assert "permission_count" in data[0]
