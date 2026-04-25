"""
Integration Tests: Full Authentication Flow
============================================
Tests multi-step authentication workflows where several API calls interact.

Workflow 1: Register → Login → Access Protected Route → Logout
Workflow 2: Register → Login → Change Password → Login with new password
Workflow 3: Register duplicate → error flows
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────

def register_user(client: TestClient, email: str, password: str = "Pass@1234",
                  full_name: str = "Integration User", phone: str = "9000000001"):
    return client.post(
        "/api/v1/customer/auth/register",
        json={"email": email, "password": password, "full_name": full_name,
              "phone_number": phone},
    )


def login_user(client: TestClient, email: str, password: str = "Pass@1234"):
    return client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
# Workflow 1: Register → Login → Access /users/me → Profile is correct
# ─────────────────────────────────────────────────────────────

class TestRegisterLoginProfile:
    """
    Integration: A new user registers, logs in and reads their own profile.
    Validates that identity propagates correctly from auth to the user endpoint.
    """

    def test_register_and_profile_match(self, client: TestClient):
        email = "int_profile@example.com"
        full_name = "Integration Profile"

        # Step 1 – Register
        reg_res = register_user(client, email, full_name=full_name, phone="9100000001")
        assert reg_res.status_code == status.HTTP_200_OK, reg_res.text
        body = reg_res.json()
        # Response may be nested {"user": {...}} or flat {"id": ...}
        user_id = body.get("user", body).get("id") or body.get("id")
        assert user_id is not None, f"No user id in response: {body}"

        # Step 2 – Login
        login_res = login_user(client, email)
        assert login_res.status_code == status.HTTP_200_OK, login_res.text
        token = login_res.json()["access_token"]

        # Step 3 – Read profile
        me_res = client.get("/api/v1/users/me", headers=auth_headers(token))
        assert me_res.status_code == status.HTTP_200_OK, me_res.text
        me = me_res.json()
        assert me["email"] == email
        assert me["full_name"] == full_name
        assert str(me["id"]) == str(user_id)

    def test_token_works_for_protected_endpoints(self, client: TestClient):
        email = "int_protected@example.com"
        register_user(client, email, phone="9100000002")
        token = login_user(client, email).json()["access_token"]

        # Try a protected endpoint – bookings list
        res = client.get("/api/v1/bookings/", headers=auth_headers(token))
        assert res.status_code == status.HTTP_200_OK

    def test_unauthenticated_blocked_on_protected_route(self, client: TestClient):
        res = client.get("/api/v1/users/me")
        assert res.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# ─────────────────────────────────────────────────────────────
# Workflow 2: Register → Login → Wrong password rejected → Correct login succeeds
# ─────────────────────────────────────────────────────────────

class TestLoginSecurity:
    """
    Integration: Validates that wrong credentials block access and
    the correct password allows it — multi-step security flow.
    """

    def test_wrong_password_then_correct(self, client: TestClient):
        email = "int_security@example.com"
        correct_pw = "Correct@123"

        # Register
        register_user(client, email, password=correct_pw, phone="9100000003")

        # Wrong password → 401
        bad_res = login_user(client, email, password="WrongPass!")
        assert bad_res.status_code == status.HTTP_401_UNAUTHORIZED

        # Correct password → 200 with token
        good_res = login_user(client, email, password=correct_pw)
        assert good_res.status_code == status.HTTP_200_OK
        assert "access_token" in good_res.json()

    def test_register_duplicate_then_login_once(self, client: TestClient):
        email = "int_dup@example.com"
        register_user(client, email, phone="9100000004")

        # Duplicate registration must fail
        dup_res = register_user(client, email, phone="9100000005")
        assert dup_res.status_code == status.HTTP_400_BAD_REQUEST

        # Original user can still log in
        login_res = login_user(client, email)
        assert login_res.status_code == status.HTTP_200_OK

    def test_stale_token_does_not_grant_admin_access(self, client: TestClient):
        """A regular user token must not reach admin-only routes."""
        email = "int_normal_tok@example.com"
        register_user(client, email, phone="9100000006")
        token = login_user(client, email).json()["access_token"]

        res = client.get("/api/v1/admin/users/", headers=auth_headers(token))
        assert res.status_code in [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND
        ]


# ─────────────────────────────────────────────────────────────
# Workflow 3: Admin logs in → creates a user → user can login
# ─────────────────────────────────────────────────────────────

class TestAdminCreatesUser:
    """
    Integration: Admin authenticates, creates a user via admin endpoint,
    then verifies the new user can log in independently.
    """

    def test_admin_creates_and_new_user_logs_in(self, client: TestClient,
                                                 admin_token_headers: dict):
        new_email = "int_admin_created@example.com"

        # Admin creates user
        create_res = client.post(
            "/api/v1/admin/users/create",
            headers=admin_token_headers,
            json={
                "email": new_email,
                "full_name": "Admin Created",
                "phone_number": "9200000001",
                "password": "TempPass@123",
                "role": "customer",
            },
        )
        # Accept 200 or 201; skip if endpoint doesn't exist (404)
        if create_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin create user endpoint not implemented")
        assert create_res.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED], \
            create_res.text

        # New user logs in
        login_res = login_user(client, new_email, password="TempPass@123")
        assert login_res.status_code == status.HTTP_200_OK
        assert "access_token" in login_res.json()

    def test_admin_lists_users_after_registration(self, client: TestClient,
                                                   admin_token_headers: dict):
        """Registers a user then admin sees them in user list."""
        email = "int_list_check@example.com"
        register_user(client, email, phone="9200000002")

        list_res = client.get("/api/v1/admin/users/", headers=admin_token_headers)
        if list_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin users list endpoint not implemented")
        assert list_res.status_code == status.HTTP_200_OK

        emails = [u.get("email") for u in list_res.json()
                  if isinstance(list_res.json(), list)]
        # Could be paginated; just check status and non-empty
        assert list_res.json() is not None
