"""
Integration Tests for Admin Audit Log API
Tests GET /api/v1/admin/audit-logs and GET /api/v1/admin/audit-logs/stats
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from datetime import datetime, timedelta

from app.models.user import User
from app.models.audit_log import AuditLog
from app.api import deps
from app.core.security import get_password_hash
from app.main import app


# ── Helpers ──────────────────────────────────────────────────────────

def _create_superuser(session: Session) -> User:
    user = User(
        email="superadmin@test.com",
        phone_number="9999900000",
        full_name="Super Admin",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_normal_user(session: Session) -> User:
    user = User(
        email="normal@test.com",
        phone_number="8888800000",
        full_name="Normal User",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _seed_audit_logs(session: Session, count: int = 5, user_id: int = 1, action: str = "TEST"):
    for i in range(count):
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type="TEST",
            resource_id=str(i),
            timestamp=datetime.utcnow() - timedelta(hours=i),
        )
        session.add(log)
    session.commit()


# ── List Audit Logs ─────────────────────────────────────────────────

class TestListAuditLogs:
    def test_superuser_can_list_logs(self, client: TestClient, session: Session):
        superuser = _create_superuser(session)
        _seed_audit_logs(session, count=3)

        app.dependency_overrides[deps.get_current_user] = lambda: superuser
        try:
            response = client.get("/api/v1/admin/audit-logs/")
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 3
            assert "total" in data
        finally:
            app.dependency_overrides.clear()

    def test_pagination(self, client: TestClient, session: Session):
        superuser = _create_superuser(session)
        _seed_audit_logs(session, count=15)

        app.dependency_overrides[deps.get_current_user] = lambda: superuser
        try:
            response = client.get("/api/v1/admin/audit-logs/?skip=0&limit=5")
            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 5
        finally:
            app.dependency_overrides.clear()

    def test_filter_by_action(self, client: TestClient, session: Session):
        superuser = _create_superuser(session)
        _seed_audit_logs(session, count=3, action="LOGIN")
        _seed_audit_logs(session, count=2, action="LOGOUT")

        app.dependency_overrides[deps.get_current_user] = lambda: superuser
        try:
            response = client.get("/api/v1/admin/audit-logs/?action=LOGIN")
            assert response.status_code == 200
            data = response.json()
            assert all(log["action"] == "LOGIN" for log in data["data"])
        finally:
            app.dependency_overrides.clear()

    def test_filter_by_user_id(self, client: TestClient, session: Session):
        superuser = _create_superuser(session)
        _seed_audit_logs(session, count=3, user_id=superuser.id)
        _seed_audit_logs(session, count=2, user_id=9999)

        app.dependency_overrides[deps.get_current_user] = lambda: superuser
        try:
            response = client.get(f"/api/v1/admin/audit-logs/?user_id={superuser.id}")
            assert response.status_code == 200
            data = response.json()
            assert all(log["user_id"] == superuser.id for log in data["data"])
        finally:
            app.dependency_overrides.clear()

    def test_non_superuser_forbidden(self, client: TestClient, session: Session):
        normal_user = _create_normal_user(session)

        app.dependency_overrides[deps.get_current_user] = lambda: normal_user
        try:
            response = client.get("/api/v1/admin/audit-logs/")
            # App returns 400 for insufficient privileges
            assert response.status_code in [400, 403, 401]
        finally:
            app.dependency_overrides.clear()


# ── Stats Endpoint ──────────────────────────────────────────────────

class TestAuditStats:
    def test_stats_returns_data(self, client: TestClient, session: Session):
        superuser = _create_superuser(session)
        _seed_audit_logs(session, count=5, action="LOGIN")
        _seed_audit_logs(session, count=3, action="CREATE_USER")

        app.dependency_overrides[deps.get_current_user] = lambda: superuser
        try:
            response = client.get("/api/v1/admin/audit-logs/stats")
            assert response.status_code == 200
            data = response.json()
            assert "total_logs" in data
            assert data["total_logs"] == 8
        finally:
            app.dependency_overrides.clear()

    def test_stats_non_superuser_forbidden(self, client: TestClient, session: Session):
        normal_user = _create_normal_user(session)

        app.dependency_overrides[deps.get_current_user] = lambda: normal_user
        try:
            response = client.get("/api/v1/admin/audit-logs/stats")
            # App returns 400 for insufficient privileges
            assert response.status_code in [400, 403, 401]
        finally:
            app.dependency_overrides.clear()
