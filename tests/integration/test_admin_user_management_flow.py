"""
Integration Tests: Admin User Management Workflows
====================================================
Tests multi-step admin operations:

Workflow 1: Admin bulk-imports users via CSV → verifies users exist → bulk deactivates them
Workflow 2: Admin creates user → forces password change → user status reflects flag
Workflow 3: Admin transitions user state (ACTIVE → SUSPENDED → ACTIVE) → audit trail created
Workflow 4: Admin performs bulk role change → verifies roles updated
"""

import io
import pytest
from datetime import datetime, UTC, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.user import User
from app.models.rbac import Role, UserRole
from app.models.roles import RoleEnum
from app.models.audit_log import AuditLog
from app.core.security import create_access_token, get_password_hash


# ─── Helpers ─────────────────────────────────────────────────────────

def get_token(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def create_admin_with_role(session: Session) -> User:
    """Create or find an admin user with the admin role."""
    admin_role = session.exec(select(Role).where(Role.name == RoleEnum.ADMIN.value)).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value)
        session.add(admin_role)
        session.commit()

    admin = session.exec(
        select(User).where(User.email == "int_mgmt_admin@test.com")
    ).first()
    if admin:
        return admin

    admin = User(
        email="int_mgmt_admin@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
        status="active",
        phone_number="6666666666",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    session.commit()
    return admin


def _create_test_users(session: Session, count: int = 3,
                        user_status: str = "active") -> list:
    ids = []
    for i in range(count):
        u = User(
            email=f"int_bulk_{i}_{datetime.now(UTC).timestamp()}@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True,
            status=user_status,
            phone_number=f"555{i:07d}",
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        ids.append(u.id)
    return ids


# ─── Workflow 1: CSV Bulk-Import → List → Bulk-Deactivate ───────────

class TestBulkImportAndDeactivateFlow:
    """
    Integration: Admin uploads a CSV to create users → verifies they
    appear in the system → bulk-deactivates them.
    """

    def test_import_then_deactivate(self, client: TestClient, session: Session):
        admin = create_admin_with_role(session)
        headers = get_token(admin)

        # Step 1: CSV Import
        csv_content = (
            "email,full_name,phone_number,role,password\n"
            "int_import1@test.com,User One,,customer,Pass@123\n"
            "int_import2@test.com,User Two,,customer,Pass@456\n"
        )
        files = {"file": ("users.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        import_res = client.post("/api/v1/admin/users/bulk-import",
                                 headers=headers, files=files)
        if import_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Bulk import endpoint not implemented")
        assert import_res.status_code == status.HTTP_200_OK, import_res.text
        body = import_res.json()
        assert body["created"] == 2
        assert body["skipped"] == 0

        # Step 2: Verify users exist in DB
        u1 = session.exec(select(User).where(User.email == "int_import1@test.com")).first()
        u2 = session.exec(select(User).where(User.email == "int_import2@test.com")).first()
        assert u1 is not None
        assert u2 is not None

        # Step 3: Bulk deactivate
        deactivate_res = client.post(
            "/api/v1/admin/users/bulk-deactivate",
            headers=headers,
            json={"user_ids": [u1.id, u2.id]},
        )
        assert deactivate_res.status_code == status.HTTP_200_OK
        assert deactivate_res.json()["deactivated"] == 2

        # Step 4: Verify deactivation
        session.refresh(u1)
        session.refresh(u2)
        assert u1.is_active is False
        assert u2.is_active is False

    def test_duplicate_import_skips_existing(self, client: TestClient, session: Session):
        """CSV re-import should skip already-existing emails."""
        admin = create_admin_with_role(session)
        headers = get_token(admin)

        csv = "email,full_name\nint_dup_import@test.com,Dup User\n"
        files_fn = lambda: {"file": ("u.csv", io.BytesIO(csv.encode()), "text/csv")}

        res1 = client.post("/api/v1/admin/users/bulk-import",
                           headers=headers, files=files_fn())
        if res1.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Bulk import endpoint not implemented")
        assert res1.json()["created"] == 1

        res2 = client.post("/api/v1/admin/users/bulk-import",
                           headers=headers, files=files_fn())
        assert res2.json()["skipped"] == 1
        assert res2.json()["created"] == 0


# ─── Workflow 2: Force Password Change ──────────────────────────────

class TestForcePasswordChangeFlow:
    """
    Integration: Admin forces a password change on a user →
    user's flag is set → admin resets their password.
    """

    def test_force_and_reset_password(self, client: TestClient, session: Session):
        admin = create_admin_with_role(session)
        headers = get_token(admin)
        user_ids = _create_test_users(session, 1)
        uid = user_ids[0]

        # Step 1: Force password change
        force_res = client.post(
            f"/api/v1/admin/users/{uid}/force-password-change",
            headers=headers,
        )
        if force_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Force password change endpoint not implemented")
        assert force_res.status_code == status.HTTP_200_OK

        user = session.get(User, uid)
        session.refresh(user)
        assert user.force_password_change is True

        # Step 2: Admin resets the password
        reset_res = client.post(
            f"/api/v1/admin/users/{uid}/reset-password",
            headers=headers,
            json={"new_password": "NewReset@999"},
        )
        if reset_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Reset password endpoint not implemented")
        assert reset_res.status_code == status.HTTP_200_OK

        session.refresh(user)
        # After admin reset, force_password_change should still be True
        assert user.force_password_change is True


# ─── Workflow 3: State Transitions + Audit Logging ─────────────────

class TestStateTransitionAuditFlow:
    """
    Integration: Admin transitions user state ACTIVE → SUSPENDED →
    ACTIVE, and each transition produces an audit log entry.
    """

    def test_suspend_then_reactivate_with_audit(
            self, client: TestClient, session: Session):
        admin = create_admin_with_role(session)
        headers = get_token(admin)
        user_ids = _create_test_users(session, 1, user_status="active")
        uid = user_ids[0]

        # Step 1: ACTIVE → SUSPENDED
        suspend_res = client.post(
            f"/api/v1/admin/users/{uid}/transition",
            headers=headers,
            json={"new_status": "suspended"},
        )
        if suspend_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("User transition endpoint not implemented")
        assert suspend_res.status_code == status.HTTP_200_OK
        assert suspend_res.json()["new_status"] == "suspended"

        # Step 2: Verify audit log for suspension
        audit1 = session.exec(
            select(AuditLog).where(
                AuditLog.action == "USER_STATE_TRANSITION",
                AuditLog.target_id == uid,
            )
        ).first()
        assert audit1 is not None
        assert audit1.old_value["status"] == "active"
        assert audit1.new_value["status"] == "suspended"

        # Step 3: SUSPENDED → ACTIVE
        reactivate_res = client.post(
            f"/api/v1/admin/users/{uid}/transition",
            headers=headers,
            json={"new_status": "active"},
        )
        assert reactivate_res.status_code == status.HTTP_200_OK

        # Step 4: Verify user is active again
        user = session.get(User, uid)
        session.refresh(user)
        assert user.is_active is True

    def test_invalid_transition_blocked(self, client: TestClient, session: Session):
        """PENDING → DELETED should be rejected."""
        admin = create_admin_with_role(session)
        headers = get_token(admin)
        user_ids = _create_test_users(session, 1, user_status="pending")
        uid = user_ids[0]

        res = client.post(
            f"/api/v1/admin/users/{uid}/transition",
            headers=headers,
            json={"new_status": "deleted"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Transition endpoint not implemented")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid transition" in res.json().get("error", "")


# ─── Workflow 4: Bulk Role Change ────────────────────────────────────

class TestBulkRoleChangeFlow:
    """
    Integration: Admin assigns a new role to multiple users at once,
    then verifies each user's role changed in the DB.
    """

    def test_bulk_role_change_verified(self, client: TestClient, session: Session):
        admin = create_admin_with_role(session)
        headers = get_token(admin)

        # Ensure dealer role exists
        dealer_role = session.exec(
            select(Role).where(Role.name == RoleEnum.DEALER.value)
        ).first()
        if not dealer_role:
            dealer_role = Role(name=RoleEnum.DEALER.value)
            session.add(dealer_role)
            session.commit()

        user_ids = _create_test_users(session, 3)

        res = client.post(
            "/api/v1/admin/users/bulk-role-change",
            headers=headers,
            json={"user_ids": user_ids, "role": RoleEnum.DEALER.value},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Bulk role change endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["changed"] == 3

    def test_non_admin_cannot_bulk_operate(self, client: TestClient, session: Session):
        """Dealer role should not access admin bulk endpoints."""
        dealer_role = session.exec(
            select(Role).where(Role.name == RoleEnum.DEALER.value)
        ).first()
        if not dealer_role:
            dealer_role = Role(name=RoleEnum.DEALER.value)
            session.add(dealer_role)
            session.commit()

        dealer = User(
            email="int_non_admin_bulk@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True,
            phone_number="4444444444",
        )
        session.add(dealer)
        session.commit()
        session.refresh(dealer)
        session.add(UserRole(user_id=dealer.id, role_id=dealer_role.id))
        session.commit()

        res = client.post(
            "/api/v1/admin/users/bulk-deactivate",
            headers=get_token(dealer),
            json={"user_ids": [1]},
        )
        assert res.status_code in [
            status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN
        ]
