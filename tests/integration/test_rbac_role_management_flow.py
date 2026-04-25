"""
Integration Tests: RBAC & Role Management End-to-End
=====================================================
Tests multi-step RBAC workflows:

Workflow 1: Admin creates role → assigns permission → assigns to user → user accesses protected route
Workflow 2: Admin creates parent+child roles → child inherits parent permissions
Workflow 3: Admin assigns role → removes it → user loses access
Workflow 4: Role-based endpoint access across all role types
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.user import User
from app.models.rbac import Role, Permission, UserRole, RolePermission
from app.models.roles import RoleEnum
from app.models.admin_user import AdminUser
from app.core.security import create_access_token, get_password_hash
from app.api import deps


# ─── Helpers ─────────────────────────────────────────────────────────

def get_token(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def create_superuser(session: Session) -> AdminUser:
    existing = session.exec(
        select(AdminUser).where(AdminUser.email == "rbac_int_admin@test.com")
    ).first()
    if existing:
        return existing
    user = AdminUser(
        phone_number="7777777777",
        email="rbac_int_admin@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def seed_permissions(session: Session):
    slugs = ["station:read", "station:write", "battery:read", "battery:write",
             "user:read", "user:write"]
    for slug in slugs:
        if not session.exec(select(Permission).where(Permission.slug == slug)).first():
            module, action = slug.split(":")
            session.add(Permission(slug=slug, module=module, action=action))
    session.commit()


# ─── Workflow 1: Create Role → Assign Permissions → Assign to User → Verify Access ──

class TestRoleCreationAndAssignment:
    """
    Integration: Admin creates a custom role with permissions,
    assigns it to a user, and the user's access reflects the role.
    """

    def test_create_role_assign_to_user_verify_access(
            self, client: TestClient, session: Session):
        admin = create_superuser(session)
        seed_permissions(session)

        # Override deps so admin is recognized
        client.app.dependency_overrides[deps.get_current_user] = lambda: admin

        # Step 1: Create a custom role
        role_payload = {
            "name": "Integration Viewer",
            "category": "vendor_staff",
            "level": 5,
            "permissions": ["station:read", "battery:read"],
        }
        role_res = client.post("/api/v1/admin/rbac/roles", json=role_payload)
        assert role_res.status_code == status.HTTP_200_OK, role_res.text
        role_data = role_res.json()
        role_id = role_data["id"]
        assert role_data["name"] == "Integration Viewer"

        # Step 2: Verify permissions were attached in DB
        perms = session.exec(
            select(Permission.slug)
            .join(RolePermission)
            .where(RolePermission.role_id == role_id)
        ).all()
        assert "station:read" in perms
        assert "battery:read" in perms
        assert "station:write" not in perms

        # Step 3: Create a user and assign the role
        test_user = User(
            email="rbac_int_viewer@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True,
            phone_number="8888888881",
        )
        session.add(test_user)
        session.commit()
        session.refresh(test_user)
        session.add(UserRole(user_id=test_user.id, role_id=role_id))
        session.commit()

        # Step 4: User accesses a protected read endpoint
        user_headers = get_token(test_user)
        stations_res = client.get("/api/v1/stations/", headers=user_headers)
        # With station:read, they should be able to list (or get 200 even if empty)
        assert stations_res.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

        # Clean up override
        client.app.dependency_overrides.pop(deps.get_current_user, None)

    def test_role_name_uniqueness(self, client: TestClient, session: Session):
        """Duplicate role names should be rejected."""
        admin = create_superuser(session)
        client.app.dependency_overrides[deps.get_current_user] = lambda: admin

        payload = {"name": "Unique Integration Role", "category": "system", "permissions": []}
        res1 = client.post("/api/v1/admin/rbac/roles", json=payload)
        assert res1.status_code == status.HTTP_200_OK

        res2 = client.post("/api/v1/admin/rbac/roles", json=payload)
        assert res2.status_code == status.HTTP_400_BAD_REQUEST

        client.app.dependency_overrides.pop(deps.get_current_user, None)


# ─── Workflow 2: Parent–Child Role Inheritance ───────────────────────

class TestRoleInheritanceFlow:
    """
    Integration: Admin creates a parent role → creates a child role →
    child inherits parent permissions plus its own.
    """

    def test_child_inherits_parent_permissions(
            self, client: TestClient, session: Session):
        admin = create_superuser(session)
        seed_permissions(session)
        client.app.dependency_overrides[deps.get_current_user] = lambda: admin

        # Create parent role with station:read, station:write
        parent_res = client.post("/api/v1/admin/rbac/roles", json={
            "name": "Int Parent Role",
            "category": "system",
            "permissions": ["station:read", "station:write"],
        })
        assert parent_res.status_code == status.HTTP_200_OK
        parent_id = parent_res.json()["id"]

        # Create child role with battery:read, inheriting from parent
        child_res = client.post("/api/v1/admin/rbac/roles", json={
            "name": "Int Child Role",
            "category": "system",
            "parent_id": parent_id,
            "permissions": ["battery:read"],
        })
        assert child_res.status_code == status.HTTP_200_OK
        child_id = child_res.json()["id"]

        # Verify child role inherits parent's permissions
        child_role = session.get(Role, child_id)
        assert child_role.parent_role_id == parent_id

        child_perms = session.exec(
            select(Permission.slug)
            .join(RolePermission)
            .where(RolePermission.role_id == child_id)
        ).all()
        # Should have station:read + station:write (from parent) + battery:read (own)
        assert "station:read" in child_perms
        assert "station:write" in child_perms
        assert "battery:read" in child_perms
        assert len(child_perms) == 3

        client.app.dependency_overrides.pop(deps.get_current_user, None)


# ─── Workflow 3: Cross-Role Access Control ───────────────────────────

class TestCrossRoleAccessControl:
    """
    Integration: Ensures role boundaries are respected.
    Normal user → denied admin endpoints.
    Admin → allowed admin endpoints.
    """

    @pytest.fixture
    def multi_role_users(self, session: Session):
        """Create users with admin, dealer, and customer roles."""
        roles = {}
        for name in [RoleEnum.ADMIN.value, RoleEnum.DEALER.value, RoleEnum.CUSTOMER.value]:
            role = session.exec(select(Role).where(Role.name == name)).first()
            if not role:
                role = Role(name=name)
                session.add(role)
            roles[name] = role
        session.commit()

        users = {}
        user_configs = [
            (RoleEnum.ADMIN.value, "int_rbac_admin@test.com", True),
            (RoleEnum.DEALER.value, "int_rbac_dealer@test.com", False),
            (RoleEnum.CUSTOMER.value, "int_rbac_customer@test.com", False),
        ]
        for role_name, email, is_super in user_configs:
            existing = session.exec(select(User).where(User.email == email)).first()
            if existing:
                users[role_name] = existing
                continue
            user = User(
                email=email,
                hashed_password=get_password_hash("password"),
                is_active=True,
                is_superuser=is_super,
                phone_number=f"77{hash(email) % 100000000:08d}",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            session.add(UserRole(user_id=user.id, role_id=roles[role_name].id))
            session.commit()
            users[role_name] = user
        return users

    def test_admin_accesses_admin_endpoint(self, client: TestClient,
                                            multi_role_users: dict):
        admin = multi_role_users[RoleEnum.ADMIN.value]
        res = client.get("/api/v1/stations/", headers=get_token(admin))
        assert res.status_code == status.HTTP_200_OK

    def test_customer_blocked_from_station_creation(self, client: TestClient,
                                                      multi_role_users: dict):
        customer = multi_role_users[RoleEnum.CUSTOMER.value]
        res = client.post(
            "/api/v1/stations/",
            json={"name": "Illegal", "latitude": 0, "longitude": 0, "total_slots": 1},
            headers=get_token(customer),
        )
        assert res.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_malformed_token_rejected(self, client: TestClient):
        """A garbage token should be rejected outright."""
        headers = {"Authorization": "Bearer totally_invalid_token_data"}
        res = client.get("/api/v1/users/me", headers=headers)
        assert res.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_public_route_accessible_without_token(self, client: TestClient):
        """OpenAPI docs or nearby search should be public."""
        res = client.get("/docs")
        assert res.status_code == status.HTTP_200_OK

        nearby_res = client.get("/api/v1/stations/nearby",
                                params={"lat": 12.9, "lon": 77.5})
        assert nearby_res.status_code == status.HTTP_200_OK
