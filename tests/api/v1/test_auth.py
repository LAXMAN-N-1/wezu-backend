from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlmodel import select

from app.api import deps
from app.core.config import settings
from app.models.user import User
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
