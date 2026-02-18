"""
Integration Tests — Audit Log Record Creation via Endpoints
Verifies that calling auth endpoints actually creates AuditLog records.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.user import User
from app.models.audit_log import AuditLog
from app.api import deps
from app.core.security import get_password_hash
from app.main import app


# ── Helpers ──────────────────────────────────────────────────────────

def _register_user(client: TestClient, email="audit@test.com", phone="7777700000"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Audit Test User",
            "phone_number": phone,
        },
    )


def _create_user_with_password(session: Session, email="login@test.com", phone="6666600000"):
    """Create a user with a known password and ensure driver role is assigned."""
    user = User(
        email=email,
        phone_number=phone,
        full_name="Login Test",
        hashed_password=get_password_hash("Password123!"),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Get the driver role that was already seeded by conftest
    from app.models.rbac import Role
    role = session.exec(select(Role).where(Role.name == "driver")).first()
    if role and role not in user.roles:
        user.roles.append(role)
        session.add(user)
        try:
            session.commit()
        except Exception:
            session.rollback()
        session.refresh(user)
    return user


# ── Register Audit ──────────────────────────────────────────────────

class TestRegisterAudit:
    def test_register_creates_audit_log(self, client: TestClient, session: Session):
        response = _register_user(client)
        assert response.status_code == 200

        logs = session.exec(
            select(AuditLog).where(AuditLog.action == "REGISTER")
        ).all()
        assert len(logs) >= 1
        assert logs[0].resource_type == "AUTH"


# ── Login Audit ─────────────────────────────────────────────────────

class TestLoginAudit:
    def test_successful_login_creates_audit_log(self, client: TestClient, session: Session):
        user = _create_user_with_password(session)

        # The /login endpoint uses LoginRequest model (JSON body)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": user.email, "password": "Password123!"},
        )
        assert response.status_code == 200

        logs = session.exec(
            select(AuditLog).where(
                AuditLog.action == "LOGIN",
                AuditLog.user_id == user.id,
            )
        ).all()
        assert len(logs) >= 1

    def test_failed_login_wrong_password(self, client: TestClient, session: Session):
        user = _create_user_with_password(session, email="fail1@test.com", phone="5555500001")

        response = client.post(
            "/api/v1/auth/login",
            json={"username": user.email, "password": "WrongPassword!"},
        )
        assert response.status_code == 401

        logs = session.exec(
            select(AuditLog).where(
                AuditLog.action == "FAILED_LOGIN",
                AuditLog.user_id == user.id,
            )
        ).all()
        assert len(logs) >= 1

    def test_failed_login_unknown_user(self, client: TestClient, session: Session):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody@test.com", "password": "Whatever123!"},
        )
        # Should get 401 for invalid credentials
        assert response.status_code == 401

        logs = session.exec(
            select(AuditLog).where(AuditLog.action == "FAILED_LOGIN")
        ).all()
        assert len(logs) >= 1
        # user_not_found should have metadata
        found = any(
            log.meta_data and log.meta_data.get("reason") == "user_not_found"
            for log in logs
        )
        assert found, "Expected FAILED_LOGIN with reason=user_not_found"


# ── Logout Audit ────────────────────────────────────────────────────

class TestLogoutAudit:
    def test_logout_creates_audit_log(self, client: TestClient, session: Session):
        user = _create_user_with_password(session, email="logout@test.com", phone="4444400000")

        # Login first to get token
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": user.email, "password": "Password123!"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        assert token is not None

        # Override current_user for logout
        app.dependency_overrides[deps.get_current_user] = lambda: user

        try:
            response = client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200

            logs = session.exec(
                select(AuditLog).where(
                    AuditLog.action == "LOGOUT",
                    AuditLog.user_id == user.id,
                )
            ).all()
            assert len(logs) >= 1
        finally:
            app.dependency_overrides.clear()
