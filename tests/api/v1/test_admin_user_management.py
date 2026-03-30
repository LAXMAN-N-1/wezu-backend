import io
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, UTC, timedelta

from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.models.password_history import PasswordHistory
from app.models.audit_log import AuditLog


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

    admin = User(
        email="admin_mgmt@test.com", hashed_password="pw",
        is_active=True, is_superuser=True, status="active",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    session.add(UserRole(user_id=admin.id, role_id=roles[RoleEnum.ADMIN.value].id))

    dealer = User(
        email="dealer_mgmt@test.com", hashed_password="pw",
        is_active=True, status="active",
    )
    session.add(dealer)
    session.commit()
    session.refresh(dealer)
    session.add(UserRole(user_id=dealer.id, role_id=roles[RoleEnum.DEALER.value].id))

    session.commit()
    return {"admin": admin, "dealer": dealer, "roles": roles}


def get_token(user: User):
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _create_test_users(session, count=3, status="active"):
    """Create N test users and return their IDs."""
    ids = []
    for i in range(count):
        u = User(
            email=f"bulk_test_{i}_{datetime.now(UTC).timestamp()}@test.com",
            hashed_password="pw", is_active=True, status=status,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        ids.append(u.id)
    return ids


# ─── Bulk Operations ───

class TestBulkImport:
    def test_bulk_import_csv(self, client, session, mock_users_and_roles):
        """#1: CSV upload creates multiple users."""
        headers = get_token(mock_users_and_roles["admin"])
        csv_content = "email,full_name,phone_number,role,password\nimport1@test.com,User One,,customer,Pass@123\nimport2@test.com,User Two,,customer,Pass@456\n"
        files = {"file": ("users.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post("/api/v1/admin/users/bulk-import", headers=headers, files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 2
        assert body["skipped"] == 0

    def test_bulk_import_invalid_csv(self, client, session, mock_users_and_roles):
        """#2: CSV missing required columns returns error."""
        headers = get_token(mock_users_and_roles["admin"])
        csv_content = "phone,name\n1234,John\n"
        files = {"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post("/api/v1/admin/users/bulk-import", headers=headers, files=files)
        assert resp.status_code == 400

    def test_bulk_import_handles_duplicates(self, client, session, mock_users_and_roles):
        """#14: Existing emails skipped gracefully."""
        headers = get_token(mock_users_and_roles["admin"])
        # Import once
        csv1 = "email,full_name\ndup_test@test.com,Dup User\n"
        client.post("/api/v1/admin/users/bulk-import", headers=headers,
                     files={"file": ("u.csv", io.BytesIO(csv1.encode()), "text/csv")})
        # Import again
        resp = client.post("/api/v1/admin/users/bulk-import", headers=headers,
                           files={"file": ("u.csv", io.BytesIO(csv1.encode()), "text/csv")})
        assert resp.json()["skipped"] == 1
        assert resp.json()["created"] == 0


class TestBulkDeactivate:
    def test_bulk_deactivate(self, client, session, mock_users_and_roles):
        """#3: Multiple users deactivated."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 3)
        resp = client.post(
            "/api/v1/admin/users/bulk-deactivate",
            headers=headers,
            json={"user_ids": user_ids},
        )
        assert resp.status_code == 200
        assert resp.json()["deactivated"] == 3

        for uid in user_ids:
            u = session.get(User, uid)
            session.refresh(u)
            assert u.is_active is False
            assert u.status == "suspended"


class TestBulkRoleChange:
    def test_bulk_role_change(self, client, session, mock_users_and_roles):
        """#4: All target users get new role."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 2)
        resp = client.post(
            "/api/v1/admin/users/bulk-role-change",
            headers=headers,
            json={"user_ids": user_ids, "role": RoleEnum.DEALER.value},
        )
        assert resp.status_code == 200
        assert resp.json()["changed"] == 2


# ─── Password Management ───

class TestPasswordHistory:
    def test_password_history_prevents_reuse(self, client, session, mock_users_and_roles):
        """#5: Reusing a recent password is rejected."""
        from app.core.security import get_password_hash
        from app.services.password_service import PasswordService

        user_ids = _create_test_users(session, 1)
        uid = user_ids[0]

        # Record a password
        hashed = get_password_hash("MySecret@1")
        PasswordService.record_password_change(session, uid, hashed)

        # Try to reuse it
        safe = PasswordService.check_password_history(session, uid, "MySecret@1")
        assert safe is False

    def test_password_history_allows_old(self, client, session, mock_users_and_roles):
        """#6: Password older than last 5 is accepted."""
        from app.core.security import get_password_hash
        from app.services.password_service import PasswordService

        user_ids = _create_test_users(session, 1)
        uid = user_ids[0]

        # Record 6 different passwords to push the first one out
        for i in range(6):
            hashed = get_password_hash(f"Pass{i}@Xyz")
            PasswordService.record_password_change(session, uid, hashed)

        # The first one should now be allowed
        safe = PasswordService.check_password_history(session, uid, "Pass0@Xyz")
        assert safe is True

    def test_password_expiry_check(self, client, session, mock_users_and_roles):
        """#7: 90-day-old password flagged as expired."""
        from app.services.password_service import PasswordService

        user_ids = _create_test_users(session, 1)
        user = session.get(User, user_ids[0])
        user.password_changed_at = datetime.now(UTC) - timedelta(days=91)
        session.add(user)
        session.commit()
        session.refresh(user)

        assert PasswordService.is_password_expired(user) is True

    def test_force_password_change_flag(self, client, session, mock_users_and_roles):
        """#8: Admin can set force-password-change flag."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 1)

        resp = client.post(
            f"/api/v1/admin/users/{user_ids[0]}/force-password-change",
            headers=headers,
        )
        assert resp.status_code == 200

        user = session.get(User, user_ids[0])
        session.refresh(user)
        assert user.force_password_change is True

    def test_admin_reset_password(self, client, session, mock_users_and_roles):
        """#9: Admin resets user password."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 1)

        resp = client.post(
            f"/api/v1/admin/users/{user_ids[0]}/reset-password",
            headers=headers,
            json={"new_password": "NewTempPass@999"},
        )
        assert resp.status_code == 200

        user = session.get(User, user_ids[0])
        session.refresh(user)
        assert user.force_password_change is True


# ─── State Transitions ───

class TestStateTransitions:
    def test_valid_state_transition(self, client, session, mock_users_and_roles):
        """#10: PENDING→VERIFIED and ACTIVE→SUSPENDED work."""
        headers = get_token(mock_users_and_roles["admin"])

        # Create user with "pending" status
        user_ids = _create_test_users(session, 1, status="pending")

        resp = client.post(
            f"/api/v1/admin/users/{user_ids[0]}/transition",
            headers=headers,
            json={"new_status": "verified"},
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "verified"

    def test_invalid_state_transition(self, client, session, mock_users_and_roles):
        """#11: PENDING→DELETED blocked."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 1, status="pending")

        resp = client.post(
            f"/api/v1/admin/users/{user_ids[0]}/transition",
            headers=headers,
            json={"new_status": "deleted"},
        )
        assert resp.status_code == 400
        assert "Invalid transition" in resp.json()["error"]

    def test_transition_audit_logged(self, client, session, mock_users_and_roles):
        """#12: State change creates audit log."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 1, status="active")

        client.post(
            f"/api/v1/admin/users/{user_ids[0]}/transition",
            headers=headers,
            json={"new_status": "suspended"},
        )

        log = session.exec(
            select(AuditLog).where(
                AuditLog.action == "USER_STATE_TRANSITION",
                AuditLog.target_id == user_ids[0],
            )
        ).first()
        assert log is not None
        assert log.old_value["status"] == "active"
        assert log.new_value["status"] == "suspended"

    def test_suspended_to_active_transition(self, client, session, mock_users_and_roles):
        """#15: Unsuspend works correctly."""
        headers = get_token(mock_users_and_roles["admin"])
        user_ids = _create_test_users(session, 1, status="suspended")

        resp = client.post(
            f"/api/v1/admin/users/{user_ids[0]}/transition",
            headers=headers,
            json={"new_status": "active"},
        )
        assert resp.status_code == 200
        user = session.get(User, user_ids[0])
        session.refresh(user)
        assert user.is_active is True


# ─── RBAC ───

class TestBulkRBAC:
    def test_bulk_operations_non_admin_denied(self, client, session, mock_users_and_roles):
        """#13: Dealer gets 400/403 on bulk endpoints."""
        dealer = mock_users_and_roles["dealer"]
        headers = get_token(dealer)

        resp = client.post(
            "/api/v1/admin/users/bulk-deactivate",
            headers=headers,
            json={"user_ids": [1]},
        )
        assert resp.status_code in (400, 403)
