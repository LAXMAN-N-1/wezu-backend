import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.models.address import Address

def create_superuser_role_list(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@rolelist.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='3098579499', 
        email="admin@rolelist.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_get_users_by_role(client: TestClient, session: Session):
    admin = create_superuser_role_list(session)
    
    # Setup Role
    role = Role(name="Region Role", is_active=True)
    session.add(role)
    session.commit()
    
    # Setup Users and Addresses
    # U1: Active, Region "Bangalore"
    u1 = User(phone_number='2396822985', email="u1@test.com", is_active=True, full_name="User One")
    session.add(u1)
    session.commit()
    session.add(Address(user_id=u1.id, street_address="123", city="Bangalore", state="KA", postal_code="560001"))
    session.add(UserRole(user_id=u1.id, role_id=role.id))
    
    # U2: Inactive, Region "Bangalore"
    u2 = User(phone_number='1085873042', email="u2@test.com", is_active=False, full_name="User Two")
    session.add(u2)
    session.commit()
    session.add(Address(user_id=u2.id, street_address="456", city="Bangalore", state="KA", postal_code="560001"))
    session.add(UserRole(user_id=u2.id, role_id=role.id))
    
    # U3: Active, Region "Mumbai"
    u3 = User(phone_number='1742449888', email="u3@test.com", is_active=True, full_name="User Three")
    session.add(u3)
    session.commit()
    session.add(Address(user_id=u3.id, street_address="789", city="Mumbai", state="MH", postal_code="400001"))
    session.add(UserRole(user_id=u3.id, role_id=role.id))
    
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Case 1: List All for Role
    resp = client.get(f"/api/v1/admin/rbac/roles/{role.id}/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    
    # Case 2: Active Only
    resp = client.get(f"/api/v1/admin/rbac/roles/{role.id}/users?active_only=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    users = [u["email"] for u in data["items"]]
    assert "u1@test.com" in users
    assert "u3@test.com" in users
    assert "u2@test.com" not in users
    
    # Case 3: Region Filter (Bangalore)
    resp = client.get(f"/api/v1/admin/rbac/roles/{role.id}/users?region=Bangalore")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2 # u1 and u2 match Bangalore
    users = [u["email"] for u in data["items"]]
    assert "u1@test.com" in users
    assert "u2@test.com" in users
    
    # Case 4: Region + Active
    resp = client.get(f"/api/v1/admin/rbac/roles/{role.id}/users?region=Bangalore&active_only=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1 # Only u1
    assert data["items"][0]["email"] == "u1@test.com"
    
    # Case 5: CSV Export
    resp = client.get(f"/api/v1/admin/rbac/roles/{role.id}/users?export_csv=true")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Total 3 users" not in resp.text # It's CSV data
    assert "User One" in resp.text
    assert "User Two" in resp.text
    assert "User Three" in resp.text
