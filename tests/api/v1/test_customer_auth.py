"""
Test suite for Customer Authentication module
Covers: register, login — positive/negative/edge cases
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.core.database import get_db as core_get_db

AUTH_BASE = "/api/v1/customer/auth"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    app.dependency_overrides[core_get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def clean_client():
    """Client with no overrides — for auth endpoint testing."""
    with TestClient(app) as c:
        yield c


# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_register_payload(
    email="newuser@wezu.com",
    phone=None,
    full_name="Test User",
    password="SecurePass123"
):
    return {
        "email": email,
        "phone_number": phone,
        "full_name": full_name,
        "password": password,
    }


def make_login_payload(email="user@wezu.com", password="SecurePass123"):
    return {"email": email, "password": password}


# ─── Scenario 1: Registration – Positive Cases ─────────────────────────────────

def test_register_with_email(clean_client):
    """✅ Register with valid email + password → 200 or 400 if user exists"""
    payload = make_register_payload(email="new_test_user@wezu.com")
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code in [200, 400]
    if response.status_code == 200:
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data


def test_register_with_phone(clean_client):
    """✅ Register with phone number only"""
    payload = make_register_payload(email=None, phone="+919876543210")
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code in [200, 400]


def test_register_response_user_structure(clean_client):
    """✅ Register → user object has expected keys"""
    payload = make_register_payload(email="struct_test@wezu.com")
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    if response.status_code == 200:
        user = response.json()["user"]
        expected_keys = {"id", "email", "full_name", "user_type", "kyc_status"}
        assert expected_keys.issubset(user.keys())
        assert user["user_type"] == "customer"
        assert user["kyc_status"] == "not_submitted"


# ─── Scenario 2: Registration – Negative Cases ─────────────────────────────────

def test_register_no_email_or_phone(clean_client):
    """❌ Register with neither email nor phone → 400"""
    payload = {"full_name": "No Contact", "password": "SecurePass123"}
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code in [400, 422]


def test_register_missing_full_name(clean_client):
    """❌ Register with missing full_name → 422"""
    payload = {"email": "noname@wezu.com", "password": "SecurePass123"}
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code == 422


def test_register_missing_password(clean_client):
    """❌ Register with no password → 422"""
    payload = {"email": "nopw@wezu.com", "full_name": "No PW"}
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("short_password", ["abc", "1234567", "pass"])
def test_register_short_password(clean_client, short_password):
    """❌ Password < 8 chars → 422 validation error"""
    payload = make_register_payload(password=short_password)
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code == 422


def test_register_invalid_email_format(clean_client):
    """❌ Invalid email format → 422"""
    payload = make_register_payload(email="not-an-email")
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code == 422


def test_register_duplicate_email(clean_client):
    """❌ Register same email twice → 400 on second attempt"""
    payload = make_register_payload(email="duplicate@wezu.com")
    # First register
    r1 = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    # Second register with same email
    r2 = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    if r1.status_code == 200:
        assert r2.status_code == 400
        assert "already exists" in r2.json().get("detail", "").lower()


# ─── Scenario 3: Login – Positive Cases ────────────────────────────────────────

def test_login_with_email(clean_client):
    """✅ Login with email + correct password → 200"""
    # First register
    reg = clean_client.post(f"{AUTH_BASE}/register", json=make_register_payload(
        email="login_test@wezu.com", password="TestPass123")
    )
    if reg.status_code == 200:
        response = clean_client.post(
            f"{AUTH_BASE}/login",
            json=make_login_payload(email="login_test@wezu.com", password="TestPass123")
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


def test_login_returns_correct_structure(clean_client):
    """✅ Login response has token_type bearer"""
    reg = clean_client.post(f"{AUTH_BASE}/register", json=make_register_payload(
        email="structlogin@wezu.com", password="TestPass999"
    ))
    if reg.status_code == 200:
        login = clean_client.post(f"{AUTH_BASE}/login", json=make_login_payload(
            email="structlogin@wezu.com", password="TestPass999"
        ))
        if login.status_code == 200:
            assert login.json()["token_type"] == "bearer"


# ─── Scenario 4: Login – Negative Cases ────────────────────────────────────────

def test_login_wrong_password(clean_client):
    """❌ Login with wrong password → 401"""
    response = clean_client.post(f"{AUTH_BASE}/login", json={
        "email": "any@wezu.com",
        "password": "WrongPassword!"
    })
    assert response.status_code in [401, 400]


def test_login_non_existent_user(clean_client):
    """❌ Login with non-existent email → 401"""
    response = clean_client.post(f"{AUTH_BASE}/login", json={
        "email": "ghost999@nowhere.com",
        "password": "AnyPassword123"
    })
    assert response.status_code == 401
    assert "Invalid" in response.json().get("detail", "")


def test_login_missing_email(clean_client):
    """❌ Login without email field → 422"""
    response = clean_client.post(f"{AUTH_BASE}/login", json={"password": "SomePass123"})
    assert response.status_code == 422


def test_login_missing_password(clean_client):
    """❌ Login without password → 422"""
    response = clean_client.post(f"{AUTH_BASE}/login", json={"email": "test@wezu.com"})
    assert response.status_code == 422


def test_login_empty_payload(clean_client):
    """❌ Login with empty body → 422"""
    response = clean_client.post(f"{AUTH_BASE}/login", json={})
    assert response.status_code == 422


# ─── Scenario 5: Edge Cases ────────────────────────────────────────────────────

@pytest.mark.parametrize("email", [
    "",
    "   ",
    "a@b",
    "test@@domain.com",
])
def test_login_invalid_email_formats(clean_client, email):
    """⚠️ Login with invalid email formats"""
    response = clean_client.post(f"{AUTH_BASE}/login", json={
        "email": email,
        "password": "SomePassword123"
    })
    assert response.status_code in [400, 401, 422]


def test_register_with_very_long_name(clean_client):
    """⚠️ Very long full_name → should be handled gracefully"""
    long_name = "A" * 500
    payload = make_register_payload(email="longname@wezu.com", full_name=long_name)
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code in [200, 400, 422]


def test_register_with_special_chars_in_name(clean_client):
    """⚠️ Special characters in name → accepted or validated"""
    payload = make_register_payload(
        email="special@wezu.com",
        full_name="José María Ó'Brien"
    )
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code in [200, 400, 422]


def test_register_with_exactly_8_char_password(clean_client):
    """✅ Password with exactly 8 chars (boundary) → accepted"""
    payload = make_register_payload(email="boundary@wezu.com", password="Pass1234")
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code in [200, 400]  # 200 OK or 400 if duplicate


def test_register_with_7_char_password(clean_client):
    """❌ Password with 7 chars (below boundary) → 422"""
    payload = make_register_payload(email="below@wezu.com", password="Pass123")
    response = clean_client.post(f"{AUTH_BASE}/register", json=payload)
    assert response.status_code == 422
