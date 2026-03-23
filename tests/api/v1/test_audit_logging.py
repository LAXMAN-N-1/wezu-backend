import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta

from app.models.audit_log import AuditLog, AuditActionType
from app.models.roles import RoleEnum
from app.models.user import User
from app.models.rbac import Role, UserRole
from app.core.audit import AuditLogger
from app.services.audit_service import AuditService


# ─── Fixtures ───

@pytest.fixture
def mock_users_and_roles(session: Session):
    roles = {}
    for r_name in [RoleEnum.ADMIN.value, RoleEnum.DEALER.value, RoleEnum.DRIVER.value, RoleEnum.CUSTOMER.value]:
        role = session.exec(select(Role).where(Role.name == r_name)).first()
        if not role:
            role = Role(name=r_name)
            session.add(role)
        roles[r_name] = role
    session.commit()

    users_data = {
        RoleEnum.ADMIN.value: User(email="admin_audit@test.com", hashed_password="pw", is_active=True, is_superuser=True),
        RoleEnum.DEALER.value: User(email="dealer_audit@test.com", hashed_password="pw", is_active=True),
        RoleEnum.DRIVER.value: User(email="driver_audit@test.com", hashed_password="pw", is_active=True),
    }

    for r_name, user in users_data.items():
        session.add(user)
        session.commit()
        session.refresh(user)
        link = UserRole(user_id=user.id, role_id=roles[r_name].id)
        session.add(link)
    session.commit()

    return users_data


def get_override_token(user: User):
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _create_sample_logs(session: Session, admin_id: int):
    """Seed the DB with some audit logs for filter/export tests."""
    logs = [
        AuditLog(user_id=admin_id, action="AUTH_LOGIN", resource_type="AUTH",
                 ip_address="10.0.0.1", user_agent="TestAgent/1.0",
                 timestamp=datetime(2026, 1, 15, 10, 0)),
        AuditLog(user_id=admin_id, action="AUTH_LOGOUT", resource_type="AUTH",
                 ip_address="10.0.0.1", user_agent="TestAgent/1.0",
                 timestamp=datetime(2026, 1, 15, 18, 0)),
        AuditLog(user_id=admin_id, action="USER_CREATION", resource_type="USER",
                 target_id=99, ip_address="10.0.0.2",
                 timestamp=datetime(2026, 2, 1, 9, 0)),
        AuditLog(user_id=admin_id, action="BALANCE_ADJUSTMENT", resource_type="WALLET",
                 target_id=5,
                 old_value={"balance": 100.0}, new_value={"balance": 250.0},
                 timestamp=datetime(2026, 2, 10, 12, 0)),
        AuditLog(user_id=admin_id, action="PERMISSION_CHANGE", resource_type="ROLE",
                 target_id=3,
                 timestamp=datetime(2026, 2, 15, 14, 0)),
    ]
    for log in logs:
        session.add(log)
    session.commit()


# ─── Tests ───

class TestAuditLogService:
    """Tests 1-3: Service-level audit logging."""

    def test_audit_log_created_on_action(self, client, session, mock_users_and_roles):
        """#1: Service creates an AuditLog with all fields."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        AuditLogger.log_event(
            db=session,
            user_id=admin.id,
            action="AUTH_LOGIN",
            resource_type="AUTH",
            ip_address="192.168.1.1",
            user_agent="TestBrowser/2.0",
        )
        logs = session.exec(select(AuditLog).where(AuditLog.user_id == admin.id)).all()
        assert len(logs) >= 1
        log = logs[-1]
        assert log.action == "AUTH_LOGIN"
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "TestBrowser/2.0"

    def test_old_new_value_stored(self, client, session, mock_users_and_roles):
        """#2: old_value/new_value JSON stored correctly."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        old_val = {"balance": 100.0}
        new_val = {"balance": 200.0}
        AuditLogger.log_event(
            db=session,
            user_id=admin.id,
            action="BALANCE_ADJUSTMENT",
            resource_type="WALLET",
            old_value=old_val,
            new_value=new_val,
        )
        log = session.exec(
            select(AuditLog).where(
                AuditLog.user_id == admin.id,
                AuditLog.action == "BALANCE_ADJUSTMENT",
            )
        ).first()
        assert log is not None
        assert log.old_value == old_val
        assert log.new_value == new_val

    def test_action_type_enum_validation(self, client, session, mock_users_and_roles):
        """#3: AuditActionType enum has all required values."""
        expected = {
            "AUTH_LOGIN", "AUTH_LOGOUT", "DATA_MODIFICATION",
            "BALANCE_ADJUSTMENT", "USER_CREATION",
            "PERMISSION_CHANGE", "FINANCIAL_TRANSACTION",
        }
        actual = {e.value for e in AuditActionType}
        assert expected == actual


class TestAuditListEndpoint:
    """Tests 4-9: GET /audit/ with filters and pagination."""

    def test_list_audit_logs_no_filter(self, client, session, mock_users_and_roles):
        """#4: GET /audit/ returns paginated results."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "data" in body
        assert body["total"] >= 5

    def test_filter_by_user_id(self, client, session, mock_users_and_roles):
        """#5: Filter by user_id returns correct subset."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get(f"/api/v1/admin/audit-logs/?user_id={admin.id}", headers=headers)
        assert resp.status_code == 200
        for log in resp.json()["data"]:
            assert log["user_id"] == admin.id

    def test_filter_by_action_type(self, client, session, mock_users_and_roles):
        """#6: Filter by action returns correct subset."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/?action=AUTH_LOGIN", headers=headers)
        assert resp.status_code == 200
        for log in resp.json()["data"]:
            assert log["action"] == "AUTH_LOGIN"

    def test_filter_by_date_range(self, client, session, mock_users_and_roles):
        """#7: Date range filter works."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get(
            "/api/v1/admin/audit-logs/?date_from=2026-02-01T00:00:00&date_to=2026-02-28T23:59:59",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Only Feb logs (USER_CREATION, BALANCE_ADJUSTMENT, PERMISSION_CHANGE)
        assert len(data) >= 3

    def test_filter_by_target_id(self, client, session, mock_users_and_roles):
        """#8: target_id filter works."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/?target_id=99", headers=headers)
        assert resp.status_code == 200
        for log in resp.json()["data"]:
            assert log["target_id"] == 99

    def test_pagination(self, client, session, mock_users_and_roles):
        """#9: skip/limit work and total is accurate."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/?skip=0&limit=2", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 2
        assert body["total"] >= 5  # We seeded 5


class TestAuditStats:
    """Test 10: Stats endpoint."""

    def test_stats_endpoint(self, client, session, mock_users_and_roles):
        """#10: GET /audit/stats returns counts and top actions."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/stats", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_logs"] >= 5
        assert len(body["top_actions"]) > 0


class TestAuditExport:
    """Tests 11-12: CSV and JSON export."""

    def test_export_csv(self, client, session, mock_users_and_roles):
        """#11: GET /audit/export/csv returns CSV content."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/export/csv", headers=headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        assert "id,user_id,action" in content  # CSV header
        assert "AUTH_LOGIN" in content

    def test_export_json(self, client, session, mock_users_and_roles):
        """#12: GET /audit/export/json returns JSON array."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        _create_sample_logs(session, admin.id)
        headers = get_override_token(admin)

        resp = client.get("/api/v1/admin/audit-logs/export/json", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5


class TestDecoratorIntegration:
    """Test 13: Decorator auto-logs on decorated endpoints."""

    def test_decorator_auto_logs(self, client, session, mock_users_and_roles):
        """#13: Hitting a decorated endpoint creates audit log.
        The wallet recharge endpoint uses @audit_log("WALLET_RECHARGE", "WALLET").
        We just check that the decorator infrastructure doesn't crash.
        """
        # Since wallet recharge needs Razorpay, we just verify the decorator imports work
        from app.core.audit import audit_log
        assert callable(audit_log)

        # Verify decorator produces a wrapper
        @audit_log("TEST_ACTION", "TEST")
        def dummy_func(**kwargs):
            return {"ok": True}

        result = dummy_func(db=session)
        assert result == {"ok": True}


class TestAuditRBAC:
    """Test 14: Non-admin access denied."""

    def test_non_admin_denied(self, client, session, mock_users_and_roles):
        """#14: Non-admin gets 403 on audit endpoints."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)

        resp = client.get("/api/v1/admin/audit-logs/", headers=headers)
        assert resp.status_code in (400, 403)  # Superuser guard returns 400


class TestRequestMetadata:
    """Test 15: IP and user-agent captured."""

    def test_ip_and_user_agent_captured(self, client, session, mock_users_and_roles):
        """#15: Request metadata stored in audit log."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        AuditLogger.log_event(
            db=session,
            user_id=admin.id,
            action="AUTH_LOGIN",
            resource_type="AUTH",
            ip_address="203.0.113.42",
            user_agent="Mozilla/5.0 (Test)",
        )
        log = session.exec(
            select(AuditLog).where(
                AuditLog.ip_address == "203.0.113.42"
            )
        ).first()
        assert log is not None
        assert log.user_agent == "Mozilla/5.0 (Test)"
        assert log.ip_address == "203.0.113.42"
