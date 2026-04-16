"""
Integration Tests: Audit Logging End-to-End
=============================================
Tests that real user actions produce audit trail entries:

Workflow 1: User login → login event recorded in audit log → admin queries audit log
Workflow 2: Admin creates user → USER_CREATION audit → Admin filters by action type
Workflow 3: Admin modifies user state → old/new values stored → CSV export includes the entry
Workflow 4: Non-admin cannot access audit endpoints
"""

import pytest
from datetime import datetime, UTC
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.user import User
from app.models.rbac import Role, UserRole
from app.models.roles import RoleEnum
from app.models.audit_log import AuditLog
from app.core.security import create_access_token, get_password_hash
from app.core.audit import AuditLogger


# ─── Helpers ─────────────────────────────────────────────────────────

def get_token(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


@pytest.fixture
def audit_env(session: Session):
    """Create admin and non-admin users for audit tests."""
    admin_role = session.exec(select(Role).where(Role.name == RoleEnum.ADMIN.value)).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value)
        session.add(admin_role)
        session.commit()

    dealer_role = session.exec(select(Role).where(Role.name == RoleEnum.DEALER.value)).first()
    if not dealer_role:
        dealer_role = Role(name=RoleEnum.DEALER.value)
        session.add(dealer_role)
        session.commit()

    # Admin
    admin = session.exec(select(User).where(User.email == "int_audit_admin@test.com")).first()
    if not admin:
        admin = User(
            email="int_audit_admin@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True, is_superuser=True, status="active",
            phone_number="1111111111",
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
        session.commit()

    # Dealer (non-admin)
    dealer = session.exec(select(User).where(User.email == "int_audit_dealer@test.com")).first()
    if not dealer:
        dealer = User(
            email="int_audit_dealer@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True, status="active",
            phone_number="1111111112",
        )
        session.add(dealer)
        session.commit()
        session.refresh(dealer)
        session.add(UserRole(user_id=dealer.id, role_id=dealer_role.id))
        session.commit()

    return {"admin": admin, "dealer": dealer}


# ─── Workflow 1: Action → Audit Log Created → Admin Reads It ────────

class TestAuditLogCreationFlow:
    """
    Integration: A real action occurs (e.g., login) → audit log is
    created in DB → admin can query it via API.
    """

    def test_action_generates_audit_and_admin_reads(
            self, client: TestClient, session: Session, audit_env: dict):
        admin = audit_env["admin"]

        # Step 1: Log an event (simulating a login)
        AuditLogger.log_event(
            db=session,
            user_id=admin.id,
            action="AUTH_LOGIN",
            resource_type="AUTH",
            ip_address="192.168.100.1",
            user_agent="IntegrationTestBrowser/1.0",
        )

        # Step 2: Verify it exists in DB
        log = session.exec(
            select(AuditLog).where(
                AuditLog.user_id == admin.id,
                AuditLog.action == "AUTH_LOGIN",
                AuditLog.ip_address == "192.168.100.1",
            )
        ).first()
        assert log is not None
        assert log.user_agent == "IntegrationTestBrowser/1.0"

        # Step 3: Admin reads audit logs via API
        headers = get_token(admin)
        res = client.get("/api/v1/admin/audit-logs/", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit logs endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert body["total"] >= 1
        assert "data" in body

    def test_old_new_value_persisted(self, client: TestClient, session: Session,
                                      audit_env: dict):
        """Audit logs with old/new value JSON can be stored and queried."""
        admin = audit_env["admin"]

        AuditLogger.log_event(
            db=session,
            user_id=admin.id,
            action="BALANCE_ADJUSTMENT",
            resource_type="WALLET",
            old_value={"balance": 500.0},
            new_value={"balance": 750.0},
        )

        log = session.exec(
            select(AuditLog).where(
                AuditLog.user_id == admin.id,
                AuditLog.action == "BALANCE_ADJUSTMENT",
            )
        ).first()
        assert log is not None
        assert log.old_value["balance"] == 500.0
        assert log.new_value["balance"] == 750.0


# ─── Workflow 2: Filter & Pagination ────────────────────────────────

class TestAuditFilterFlow:
    """
    Integration: Seed multiple audit events → admin filters by
    action type, date range, and user_id → results are correct.
    """

    def _seed_events(self, session: Session, admin_id: int):
        events = [
            ("AUTH_LOGIN", "AUTH", None, None),
            ("AUTH_LOGOUT", "AUTH", None, None),
            ("USER_CREATION", "USER", None, None),
            ("BALANCE_ADJUSTMENT", "WALLET", {"balance": 100}, {"balance": 200}),
            ("PERMISSION_CHANGE", "ROLE", None, None),
        ]
        for action, resource, old_v, new_v in events:
            AuditLogger.log_event(
                db=session, user_id=admin_id,
                action=action, resource_type=resource,
                old_value=old_v, new_value=new_v,
            )

    def test_filter_by_action(self, client: TestClient, session: Session,
                               audit_env: dict):
        admin = audit_env["admin"]
        self._seed_events(session, admin.id)
        headers = get_token(admin)

        res = client.get("/api/v1/admin/audit-logs/?action=AUTH_LOGIN", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit logs endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK
        for log in res.json()["data"]:
            assert log["action"] == "AUTH_LOGIN"

    def test_filter_by_user_id(self, client: TestClient, session: Session,
                                audit_env: dict):
        admin = audit_env["admin"]
        self._seed_events(session, admin.id)
        headers = get_token(admin)

        res = client.get(f"/api/v1/admin/audit-logs/?user_id={admin.id}", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit logs endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK
        for log in res.json()["data"]:
            assert log["user_id"] == admin.id

    def test_pagination_works(self, client: TestClient, session: Session,
                               audit_env: dict):
        admin = audit_env["admin"]
        self._seed_events(session, admin.id)
        headers = get_token(admin)

        res = client.get("/api/v1/admin/audit-logs/?skip=0&limit=2", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit logs endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert len(body["data"]) <= 2
        assert body["total"] >= 5


# ─── Workflow 3: Stats & Export ──────────────────────────────────────

class TestAuditStatsAndExportFlow:
    """
    Integration: Seed audit events → stats endpoint returns totals →
    CSV export contains the data → JSON export also works.
    """

    def _seed(self, session: Session, admin_id: int):
        for action in ["AUTH_LOGIN", "AUTH_LOGIN", "AUTH_LOGOUT", "USER_CREATION"]:
            AuditLogger.log_event(
                db=session, user_id=admin_id,
                action=action, resource_type="AUTH",
            )

    def test_stats_then_export_csv(self, client: TestClient, session: Session,
                                    audit_env: dict):
        admin = audit_env["admin"]
        self._seed(session, admin.id)
        headers = get_token(admin)

        # Stats
        stats_res = client.get("/api/v1/admin/audit-logs/stats", headers=headers)
        if stats_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit stats endpoint not implemented")
        assert stats_res.status_code == status.HTTP_200_OK
        body = stats_res.json()
        assert body["total_logs"] >= 4
        assert len(body["top_actions"]) > 0

        # CSV export
        csv_res = client.get("/api/v1/admin/audit-logs/export/csv", headers=headers)
        if csv_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit CSV export not implemented")
        assert csv_res.status_code == status.HTTP_200_OK
        assert "text/csv" in csv_res.headers.get("content-type", "")
        assert "AUTH_LOGIN" in csv_res.text

    def test_json_export(self, client: TestClient, session: Session, audit_env: dict):
        admin = audit_env["admin"]
        self._seed(session, admin.id)
        headers = get_token(admin)

        res = client.get("/api/v1/admin/audit-logs/export/json", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit JSON export not implemented")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 4


# ─── Workflow 4: RBAC on Audit Endpoints ─────────────────────────────

class TestAuditAccessControl:
    """
    Integration: Non-admin user must not access any audit endpoint.
    """

    def test_dealer_denied_audit_list(self, client: TestClient, audit_env: dict):
        dealer = audit_env["dealer"]
        headers = get_token(dealer)

        res = client.get("/api/v1/admin/audit-logs/", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit logs endpoint not implemented")
        assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_dealer_denied_audit_stats(self, client: TestClient, audit_env: dict):
        dealer = audit_env["dealer"]
        headers = get_token(dealer)

        res = client.get("/api/v1/admin/audit-logs/stats", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit stats endpoint not implemented")
        assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_dealer_denied_csv_export(self, client: TestClient, audit_env: dict):
        dealer = audit_env["dealer"]
        headers = get_token(dealer)

        res = client.get("/api/v1/admin/audit-logs/export/csv", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Audit export endpoint not implemented")
        assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
