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
    
    if admin_role not in user.roles:
        user.roles.append(admin_role)
        session.add(user)
    
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
