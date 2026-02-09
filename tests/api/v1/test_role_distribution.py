import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role
from app.core.config import settings
from fastapi.testclient import TestClient


def get_admin_auth_headers(client: TestClient, email: str = "role_dist_admin@test.com"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Role Dist Admin",
            "phone_number": str(abs(hash(email)))[:10].ljust(10, '0')
        },
    )
    
    # 2. Login
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": "Password123!"
        },
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


def test_role_distribution_endpoint(client, session: Session):
    """Test GET /admin/roles/distribution returns expected structure."""
    email = "role_dist_test@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # Ensure admin role
    user = session.exec(select(User).where(User.email == email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    if admin_role not in user.roles:
        user.roles.append(admin_role)
    
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Call endpoint
    resp = client.get(f"{settings.API_V1_STR}/admin/roles/distribution", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # Check structure
    assert "users_per_role" in data
    assert "total_users_with_roles" in data
    assert "role_growth_trends" in data
    assert "most_used_roles" in data
    assert "underutilized_roles" in data
    assert "empty_roles" in data
    assert "generated_at" in data
    
    # Check users_per_role structure
    if len(data["users_per_role"]) > 0:
        role_item = data["users_per_role"][0]
        assert "role_id" in role_item
        assert "role_name" in role_item
        assert "user_count" in role_item
        assert "percentage" in role_item


def test_role_distribution_requires_admin(client, session: Session):
    """Test that non-admins cannot access role distribution."""
    email = "regular_role_user@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # User is registered but NOT an admin
    resp = client.get(f"{settings.API_V1_STR}/admin/roles/distribution", headers=headers)
    assert resp.status_code == 403


def test_role_test_configuration(client, session: Session):
    """Test POST /admin/roles/{role_id}/test returns role preview."""
    email = "role_test_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # Ensure admin role
    user = session.exec(select(User).where(User.email == email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    if admin_role not in user.roles:
        user.roles.append(admin_role)
    
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Test the admin role
    resp = client.post(f"{settings.API_V1_STR}/admin/roles/{admin_role.id}/test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # Check structure
    assert "role_id" in data
    assert "role_name" in data
    assert "menu_structure" in data
    assert "available_screens" in data
    assert "actions_enabled" in data
    assert "data_visibility" in data
    assert "total_permissions" in data
    assert "access_level" in data


def test_bulk_role_assignment(client, session: Session):
    """Test POST /admin/roles/bulk-assign works."""
    email = "bulk_role_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # Ensure admin
    user = session.exec(select(User).where(User.email == email)).first()
    user.is_superuser = True
    session.add(user)
    session.commit()
    
    # Create test users
    target_emails = ["bulkrole1@test.com", "bulkrole2@test.com"]
    target_ids = []
    for target_email in target_emails:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": target_email,
                "password": "Password123!",
                "full_name": "Bulk Target",
                "phone_number": str(abs(hash(target_email)))[:10].ljust(10, '0')
            },
        )
        target = session.exec(select(User).where(User.email == target_email)).first()
        target_ids.append(target.id)
    
    # Get or create a role
    role = session.exec(select(Role).where(Role.name == "customer")).first()
    if not role:
        role = Role(name="customer", slug="customer", description="Customer")
        session.add(role)
        session.commit()
        session.refresh(role)
    
    # Bulk assign
    resp = client.post(
        f"{settings.API_V1_STR}/admin/roles/bulk-assign",
        json={
            "user_ids": target_ids,
            "role_id": role.id,
            "replace_existing": False
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success_count"] == 2
    assert data["failure_count"] == 0
