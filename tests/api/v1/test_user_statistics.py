import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role
from app.core.config import settings
from fastapi.testclient import TestClient


def get_admin_auth_headers(client: TestClient, email: str = "user_stats_admin@test.com"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "User Stats Admin",
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


def test_user_statistics_endpoint(client, session: Session):
    """Test GET /admin/users/statistics returns expected structure."""
    email = "user_stats_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # Ensure admin role and superuser
    user = session.exec(select(User).where(User.email == email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    # Assign role safely
    from app.models.rbac import UserRole
    from sqlalchemy.exc import IntegrityError
    
    link = UserRole(user_id=user.id, role_id=admin_role.id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Call endpoint
    resp = client.get(f"{settings.API_V1_STR}/admin/users/statistics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # Check structure
    assert "total_users" in data
    assert "active_users" in data
    assert "inactive_users" in data
    assert "deleted_users" in data
    assert "users_by_role" in data
    assert "kyc_stats" in data
    assert "growth_over_time" in data
    assert "regional_distribution" in data
    assert "generated_at" in data
    
    # KYC Stats structure
    kyc = data["kyc_stats"]
    assert "pending" in kyc
    assert "verified" in kyc
    assert "rejected" in kyc
    assert "verification_rate" in kyc
    
    # Growth has items
    assert isinstance(data["growth_over_time"], list)
    if len(data["growth_over_time"]) > 0:
        item = data["growth_over_time"][0]
        assert "period" in item
        assert "new_users" in item


def test_user_statistics_requires_admin(client, session: Session):
    """Test that non-admins cannot access statistics."""
    email = "regular_user_stats@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # User is registered but NOT an admin
    # Call endpoint
    resp = client.get(f"{settings.API_V1_STR}/admin/users/statistics", headers=headers)
    assert resp.status_code == 403


def test_user_engagement_endpoint(client, session: Session):
    """Test GET /admin/users/engagement returns expected structure."""
    email = "user_engage_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # Ensure admin role
    user = session.exec(select(User).where(User.email == email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    # Assign role safely
    from app.models.rbac import UserRole
    from sqlalchemy.exc import IntegrityError
    
    link = UserRole(user_id=user.id, role_id=admin_role.id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Call endpoint
    resp = client.get(f"{settings.API_V1_STR}/admin/users/engagement", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # Check structure
    assert "daily_active_users" in data
    assert "weekly_active_users" in data
    assert "monthly_active_users" in data
    assert "stickiness_ratio" in data
    assert "login_frequency" in data
    assert "feature_usage" in data
    assert "churn_rate_30d" in data
    assert "retention_rate_7d" in data
    assert "retention_rate_30d" in data
    assert "generated_at" in data
    
    # Login frequency structure
    login = data["login_frequency"]
    assert "daily_avg" in login
    assert "weekly_avg" in login
    assert "monthly_avg" in login


def test_impersonate_user_endpoint(client, session: Session):
    """Test POST /admin/users/{user_id}/impersonate returns token."""
    admin_email = "impersonate_admin@test.com"
    target_email = "impersonate_target@test.com"
    
    # Create admin
    admin_headers = get_admin_auth_headers(client, email=admin_email)
    
    # Create target user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": target_email,
            "password": "Password123!",
            "full_name": "Target User",
            "phone_number": "9876543210"
        },
    )
    
    # Ensure admin is super admin
    admin = session.exec(select(User).where(User.email == admin_email)).first()
    admin.is_superuser = True
    session.add(admin)
    session.commit()
    
    # Get target user
    target = session.exec(select(User).where(User.email == target_email)).first()
    
    # Impersonate
    resp = client.post(
        f"{settings.API_V1_STR}/admin/users/{target.id}/impersonate",
        json={"reason": "Testing impersonation"},
        headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # Check response structure
    assert "impersonation_token" in data
    assert "expires_at" in data
    assert "impersonated_user_id" in data
    assert data["impersonated_user_id"] == target.id
    assert "user_roles" in data
    assert "user_permissions" in data
    assert "menu_config" in data
    assert "warning" in data


def test_impersonate_requires_super_admin(client, session: Session):
    """Test that regular admins cannot impersonate."""
    email = "regular_admin_imp@test.com"
    target_email = "target_for_imp@test.com"
    
    headers = get_admin_auth_headers(client, email=email)
    
    # Register target
    client.post(
        "/api/v1/auth/register",
        json={
            "email": target_email,
            "password": "Password123!",
            "full_name": "Target",
            "phone_number": "1234567890"
        },
    )
    target = session.exec(select(User).where(User.email == target_email)).first()
    
    # Regular user (not super admin)
    resp = client.post(
        f"{settings.API_V1_STR}/admin/users/{target.id}/impersonate",
        json={"reason": "Testing"},
        headers=headers
    )
    assert resp.status_code == 403
