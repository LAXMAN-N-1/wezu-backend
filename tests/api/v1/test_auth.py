from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException, status
from sqlalchemy import text
from starlette.requests import Request
from sqlmodel import select

from app.api import deps
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserStatus, UserType
from app.models.rbac import Role, UserRole
from app.services.auth_service import AuthService

def _build_request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/v1/profile", "headers": []})

# --- POSITIVE CASES ---

def test_register_user_success(client):
    """Test successful user registration (HEAD version)"""
    email = "newuser@example.com"
    response = client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "full_name": "New User",
            "phone_number": "1234567890"
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Handle both response formats
    if "user" in data:
        assert data["user"]["email"] == email
    else:
        assert data["email"] == email
    assert "id" in (data["user"] if "user" in data else data)

def test_login_user_success(client):
    """Test successful user login after registration (HEAD version)"""
    email = "login_success@example.com"
    password = "Password123!"
    
    # Register
    client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Login Success User",
            "phone_number": "0987654321"
        },
    )
    
    # Login via /auth/token
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": password
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

# --- ADVANCED CASES (laxman/main) ---

def test_register_user_persists_uppercase_user_type(client, session):
    response = client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "enum-safe@example.com",
            "password": "Password123!",
            "full_name": "Enum Safe User",
            "phone_number": "9998887775",
        },
    )
    assert response.status_code == 200
    data = response.json()
    user_id = data["user"]["id"] if "user" in data else data["id"]

    user_type = session.execute(
        text("SELECT user_type FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    ).scalar_one()
    assert user_type == "CUSTOMER"

def test_login_repairs_legacy_lowercase_user_type(client, session):
    user = User(
        email="legacy-lowercase@example.com",
        full_name="Legacy Lowercase",
        phone_number="9998887774",
        hashed_password=get_password_hash("Password123!"),
        status=UserStatus.ACTIVE,
        user_type=UserType.CUSTOMER,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    session.execute(
        text("UPDATE users SET user_type = 'customer' WHERE id = :user_id"),
        {"user_id": user.id},
    )
    session.commit()

    response = client.post(
        "/api/v1/customer/auth/login",
        json={
            "email": "legacy-lowercase@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200

    repaired_user_type = session.execute(
        text("SELECT user_type FROM users WHERE id = :user_id"),
        {"user_id": user.id},
    ).scalar_one()
    assert repaired_user_type == "CUSTOMER"

def test_login_accepts_phone_with_country_code_prefix(client):
    client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "prefix-login@example.com",
            "password": "Password123!",
            "full_name": "Prefix Login User",
            "phone_number": "9154345918",
        },
    )

    response = client.post(
        "/api/v1/customer/auth/login",
        json={
            "email": "919154345918",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200

def test_admin_login_bootstraps_role_link_when_user_roles_missing(client, session):
    role = session.exec(select(Role).where(Role.name == "admin")).first()
    if role is None:
        role = Role(
            name="admin",
            description="Platform admin",
            category="system",
            level=100,
            is_system_role=True,
            is_active=True,
            scope_owner="global",
        )
        session.add(role)
        session.commit()
        session.refresh(role)

    user = User(
        email="bootstrap-admin@example.com",
        full_name="Bootstrap Admin",
        phone_number="9000000099",
        hashed_password=get_password_hash("Admin@123"),
        status=UserStatus.ACTIVE,
        user_type=UserType.ADMIN,
        role_id=None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "credential": "bootstrap-admin@example.com",
            "password": "Admin@123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["role"] in body["available_roles"]
    assert len(body["available_roles"]) >= 1

    session.refresh(user)
    assert user.role_id is not None

    role_link = session.exec(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == user.role_id,
        )
    ).first()
    assert role_link is not None

def test_get_current_user_supabase_mode_existing_user(session, monkeypatch):
    user = User(
        email="supabase-existing@example.com",
        full_name="Supabase Existing",
        phone_number="9000000001",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def _verify_supabase(cls, token):
        return {
            "sub": "supabase-user-123",
            "email": "supabase-existing@example.com",
            "email_verified": True,
            "role": "authenticated",
            "iat": 1713072000,
            "exp": 1893456000,
        }

    token = "supabase-existing-user-token"
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_ENFORCE_EMAIL_VERIFIED", True)
    monkeypatch.setattr(AuthService, "verify_supabase_access_token", classmethod(_verify_supabase))
    deps.invalidate_token_cache(token)

    current_user = deps.get_current_user(
        request=_build_request(),
        db=session,
        token=token,
    )
    assert current_user.id == user.id
    assert current_user.email == "supabase-existing@example.com"

def test_social_login_google_awaits_provider_verification(client, session):
    payload = {
        "email": "social-google@example.com",
        "sub": "google-sub-1",
        "name": "Google Social User",
        "picture": "https://example.com/avatar.png",
    }

    existing_user = User(
        email="social-google@example.com",
        full_name="Existing Social User",
        phone_number="9000000004",
    )
    session.add(existing_user)
    session.commit()

    with patch("app.api.v1.auth.AuthService.verify_google_token", new=AsyncMock(return_value=payload)) as verify_mock, \
         patch("app.api.v1.auth.AuthService.create_user_session", return_value=None), \
         patch("app.api.v1.auth.FraudService.calculate_risk_score", return_value=0):
        response = client.post(
            "/api/v1/auth/social-login",
            json={"provider": "google", "token": "test-social-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["user"]["email"] == "social-google@example.com"
    verify_mock.assert_awaited_once()

# --- NEGATIVE CASES ---

def test_register_duplicate_email(client):
    """Test registering with an existing email should fail"""
    email = "duplicate@example.com"
    payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "User 1",
        "phone_number": "1112223334"
    }
    # First registration
    client.post("/api/v1/customer/auth/register", json=payload)
    
    # Second registration with same email
    response = client.post("/api/v1/customer/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_login_invalid_credentials(client):
    """Test login with wrong password"""
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@test.com",
            "password": "wrong_password"
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
