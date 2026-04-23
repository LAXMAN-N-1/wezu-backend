from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
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


def test_register_user(client):
    response = client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "test@example.com",
            "password": "Password123!",
            "full_name": "Test User",
            "phone_number": "9876543210"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"
    assert "id" in data["user"]

def test_login_user(client):
    # Register first
    client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "login@example.com",
            "password": "Password123!",
            "full_name": "Login User",
             "phone_number": "9998887776"
        },
    )
    
    # Login
    response = client.post(
        "/api/v1/customer/auth/login",
        json={
            "email": "login@example.com",
            "password": "Password123!"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


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
    user_id = response.json()["user"]["id"]

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


def test_admin_login_seeds_roles_when_roles_table_is_empty(client, session):
    session.execute(text("UPDATE users SET role_id = NULL"))
    session.execute(text("DELETE FROM user_roles"))
    session.execute(text("DELETE FROM roles"))
    session.commit()
    session.expunge_all()

    user = User(
        email="legacy-seed-role@example.com",
        full_name="Legacy Seed Role",
        phone_number="9000000100",
        hashed_password=get_password_hash("Admin@123"),
        status=UserStatus.ACTIVE,
        user_type=UserType.ADMIN,
        is_superuser=True,
        role_id=None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "credential": "legacy-seed-role@example.com",
            "password": "Admin@123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["role"] in body["available_roles"]

    session.refresh(user)
    assert user.role_id is not None

    assigned_role = session.get(Role, user.role_id)
    assert assigned_role is not None
    assert assigned_role.is_active is True


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


def test_get_current_user_supabase_rejects_unverified_email(session, monkeypatch):
    user = User(
        email="supabase-unverified@example.com",
        full_name="Supabase Unverified",
        phone_number="9000000002",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def _verify_supabase(cls, token):
        return {
            "sub": "supabase-user-456",
            "email": "supabase-unverified@example.com",
            "email_verified": False,
            "role": "authenticated",
            "iat": 1713072000,
            "exp": 1893456000,
        }

    token = "supabase-unverified-user-token"
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_ENFORCE_EMAIL_VERIFIED", True)
    monkeypatch.setattr(AuthService, "verify_supabase_access_token", classmethod(_verify_supabase))
    deps.invalidate_token_cache(token)

    with pytest.raises(HTTPException) as exc_info:
        deps.get_current_user(
            request=_build_request(),
            db=session,
            token=token,
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "token_invalid"


def test_get_current_user_supabase_auto_provision(session, monkeypatch):
    def _verify_supabase(cls, token):
        return {
            "sub": "supabase-new-user-789",
            "email": "supabase-new-user@example.com",
            "email_verified": True,
            "role": "authenticated",
            "user_metadata": {"full_name": "Supabase New User"},
            "iat": 1713072000,
            "exp": 1893456000,
        }

    token = "supabase-autoprovision-token"
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_AUTO_PROVISION_USERS", True)
    monkeypatch.setattr(settings, "SUPABASE_DEFAULT_ROLE_NAME", "admin")
    monkeypatch.setattr(AuthService, "verify_supabase_access_token", classmethod(_verify_supabase))
    deps.invalidate_token_cache(token)

    current_user = deps.get_current_user(
        request=_build_request(),
        db=session,
        token=token,
    )

    assert current_user.email == "supabase-new-user@example.com"
    assert current_user.full_name == "Supabase New User"

    created_user = session.exec(
        select(User).where(User.email == "supabase-new-user@example.com")
    ).first()
    assert created_user is not None
    assert created_user.id == current_user.id
    assert created_user.role_id is not None


def test_get_current_user_hybrid_falls_back_to_supabase(session, monkeypatch):
    user = User(
        email="supabase-hybrid@example.com",
        full_name="Supabase Hybrid",
        phone_number="9000000003",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def _verify_supabase(cls, token):
        return {
            "sub": "supabase-user-hybrid",
            "email": "supabase-hybrid@example.com",
            "email_verified": True,
            "role": "authenticated",
            "iat": 1713072000,
            "exp": 1893456000,
        }

    token = "not-a-local-jwt"
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "hybrid")
    monkeypatch.setattr(AuthService, "verify_supabase_access_token", classmethod(_verify_supabase))
    deps.invalidate_token_cache(token)

    current_user = deps.get_current_user(
        request=_build_request(),
        db=session,
        token=token,
    )
    assert current_user.id == user.id


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
