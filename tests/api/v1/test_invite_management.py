"""
Tests for Invite Lifecycle Management & User Creation History endpoints.

Endpoints tested:
  - POST /api/v1/admin/users/invite       (refactored to use InviteService)
  - GET  /api/v1/admin/users/invites      (list invites)
  - POST /api/v1/admin/users/invite/{id}/resend
  - POST /api/v1/admin/users/invite/{id}/revoke
  - GET  /api/v1/admin/users/creation-history
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.core.config import settings
from app.models.user import User
from app.models.rbac import Role
from app.core.security import get_password_hash


API = settings.API_V1_STR


def _create_admin(session: Session, suffix: str = "") -> User:
    """Helper: create and persist a superuser admin."""
    admin = User(
        email=f"inv_admin{suffix}@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
        full_name=f"Invite Admin {suffix}",
        phone_number=f"900000000{suffix or '0'}",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


def _login(client: TestClient, email: str) -> str:
    """Helper: login and return access token."""
    r = client.post(
        f"{API}/auth/login",
        data={"username": email, "password": "password"},
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json()["access_token"]


def _ensure_role(session: Session, role_name: str = "customer") -> Role:
    """Helper: ensure a role exists for invite tests."""
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        role = Role(
            name=role_name,
            description=f"{role_name} role",
            is_system_role=True,
        )
        session.add(role)
        session.commit()
        session.refresh(role)
    return role


# ─── POST /invite  (refactored) ──────────────────────────────────────

def test_invite_creates_tracking_record(client: TestClient, session: Session):
    """Invite should create both a User and a UserInvite record."""
    admin = _create_admin(session, "1")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    r = client.post(
        f"{API}/admin/users/invite",
        json={"email": "new_invite@test.com", "role_name": "customer", "full_name": "Invited Person"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Invite failed: {r.text}"
    data = r.json()
    assert data["status"] == "success"
    assert "invite_id" in data
    assert "user_id" in data


def test_invite_duplicate_email_fails(client: TestClient, session: Session):
    """Inviting an existing email should return 400."""
    admin = _create_admin(session, "2")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    # First invite
    client.post(
        f"{API}/admin/users/invite",
        json={"email": "dup_invite@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Second invite - same email
    r = client.post(
        f"{API}/admin/users/invite",
        json={"email": "dup_invite@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


# ─── GET /invites ────────────────────────────────────────────────────

def test_list_invites_returns_data(client: TestClient, session: Session):
    """List invites should return paginated results."""
    admin = _create_admin(session, "3")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    # Create an invite first
    client.post(
        f"{API}/admin/users/invite",
        json={"email": "list_test@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.get(
        f"{API}/admin/users/invites",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"List invites failed: {r.text}"
    data = r.json()
    assert "items" in data
    assert "total_count" in data
    assert data["total_count"] >= 1


def test_list_invites_filter_by_status(client: TestClient, session: Session):
    """List invites filtered by status=pending should only show pending."""
    admin = _create_admin(session, "4")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    # Create an invite
    client.post(
        f"{API}/admin/users/invite",
        json={"email": "filter_test@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.get(
        f"{API}/admin/users/invites?status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["status"] == "pending"


# ─── POST /invite/{id}/resend ────────────────────────────────────────

def test_resend_invite_success(client: TestClient, session: Session):
    """Resending a pending invite should succeed and reset expiry."""
    admin = _create_admin(session, "5")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    # Create invite
    r1 = client.post(
        f"{API}/admin/users/invite",
        json={"email": "resend_test@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    invite_id = r1.json()["invite_id"]

    # Resend
    r = client.post(
        f"{API}/admin/users/invite/{invite_id}/resend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Resend failed: {r.text}"
    data = r.json()
    assert data["status"] == "success"
    assert "new_expires_at" in data


def test_resend_revoked_invite_fails(client: TestClient, session: Session):
    """Resending a revoked invite should return 400."""
    admin = _create_admin(session, "6")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    # Create + revoke
    r1 = client.post(
        f"{API}/admin/users/invite",
        json={"email": "resend_revoked@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    invite_id = r1.json()["invite_id"]

    client.post(
        f"{API}/admin/users/invite/{invite_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Try resend
    r = client.post(
        f"{API}/admin/users/invite/{invite_id}/resend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


# ─── POST /invite/{id}/revoke ───────────────────────────────────────

def test_revoke_invite_success(client: TestClient, session: Session):
    """Revoking a pending invite should set status to REVOKED."""
    admin = _create_admin(session, "7")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    # Create invite
    r1 = client.post(
        f"{API}/admin/users/invite",
        json={"email": "revoke_test@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    invite_id = r1.json()["invite_id"]

    # Revoke
    r = client.post(
        f"{API}/admin/users/invite/{invite_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Revoke failed: {r.text}"
    data = r.json()
    assert data["status"] == "success"
    assert "revoked" in data["message"].lower()


def test_revoke_already_revoked_fails(client: TestClient, session: Session):
    """Revoking an already revoked invite should return 400."""
    admin = _create_admin(session, "8")
    _ensure_role(session, "customer")
    token = _login(client, admin.email)

    r1 = client.post(
        f"{API}/admin/users/invite",
        json={"email": "double_revoke@test.com", "role_name": "customer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    invite_id = r1.json()["invite_id"]

    # First revoke
    client.post(
        f"{API}/admin/users/invite/{invite_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Second revoke
    r = client.post(
        f"{API}/admin/users/invite/{invite_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_resend_nonexistent_invite_fails(client: TestClient, session: Session):
    """Resending a non-existent invite should return 400."""
    admin = _create_admin(session, "9")
    token = _login(client, admin.email)

    r = client.post(
        f"{API}/admin/users/invite/99999/resend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


# ─── GET /creation-history ───────────────────────────────────────────

def test_creation_history_endpoint_accessible(client: TestClient, session: Session):
    """Creation history endpoint should be accessible by admin."""
    admin = _create_admin(session, "10")
    token = _login(client, admin.email)

    r = client.get(
        f"{API}/admin/users/creation-history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Creation history failed: {r.text}"
    data = r.json()
    assert "items" in data
    assert "total_count" in data
    assert "page" in data
    assert "limit" in data


def test_creation_history_unauthorized(client: TestClient, session: Session):
    """Non-admin users should not access creation history."""
    r = client.get(f"{API}/admin/users/creation-history")
    assert r.status_code in [401, 403]
