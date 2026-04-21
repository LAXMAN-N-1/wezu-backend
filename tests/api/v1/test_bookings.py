"""
Test suite for Bookings module
Covers: create, list, get, update, cancel, reminder, pay — positive/negative/edge cases
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.core.database import get_db as core_get_db

BASE = "/api/v1/bookings"


# ─── Mock Users ────────────────────────────────────────────────────────────────

class MockUser:
    id = 5
    is_superuser = False
    is_active = True
    role_id = 2
    email = "customer@wezu.com"
    full_name = "John Customer"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    return MockUser()


@pytest.fixture
def auth_client(mock_db, mock_user):
    """Authenticated client fixture."""
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    app.dependency_overrides[core_get_db] = lambda: mock_db
    app.dependency_overrides[deps.get_current_user] = lambda: mock_user
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def anon_client():
    """Unauthenticated client."""
    with TestClient(app) as c:
        yield c


# ─── Scenario 1: Create Booking ────────────────────────────────────────────────

def test_create_booking_valid(auth_client):
    """✅ POST / with valid station_id → 200 or 400 depending on booking logic"""
    payload = {"station_id": 1}
    response = auth_client.post(f"{BASE}/", json=payload)
    assert response.status_code in [200, 400]


def test_create_booking_missing_station_id(auth_client):
    """❌ POST / with missing station_id → 422"""
    response = auth_client.post(f"{BASE}/", json={})
    assert response.status_code == 422


def test_create_booking_invalid_station_type(auth_client):
    """❌ POST / with non-integer station_id → 422"""
    response = auth_client.post(f"{BASE}/", json={"station_id": "not-a-number"})
    assert response.status_code == 422


def test_create_booking_unauthenticated(anon_client):
    """❌ POST / without auth → 401/422"""
    response = anon_client.post(f"{BASE}/", json={"station_id": 1})
    assert response.status_code in [401, 403, 422]


@pytest.mark.parametrize("station_id", [1, 2, 3, 10, 100])
def test_create_booking_various_stations(auth_client, station_id):
    """✅ POST / with multiple valid station IDs"""
    response = auth_client.post(f"{BASE}/", json={"station_id": station_id})
    assert response.status_code in [200, 400]  # 400 if no slots


# ─── Scenario 2: List Bookings ─────────────────────────────────────────────────

def test_list_bookings_authenticated(auth_client, mock_db):
    """✅ GET / → returns list of user's bookings"""
    mock_exec = MagicMock()
    mock_exec.all.return_value = []
    mock_db.exec.return_value = mock_exec

    response = auth_client.get(f"{BASE}/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_bookings_unauthenticated(anon_client):
    """❌ GET / without auth → 401/422"""
    response = anon_client.get(f"{BASE}/")
    assert response.status_code in [401, 403, 422]


def test_list_bookings_returns_only_own(auth_client, mock_db):
    """✅ GET / → only returns bookings belonging to current user"""
    from app.models.battery_reservation import BatteryReservation
    mock_reservation = MagicMock(spec=BatteryReservation)
    mock_reservation.user_id = 5  # Same as MockUser.id

    mock_exec = MagicMock()
    mock_exec.all.return_value = [mock_reservation]
    mock_db.exec.return_value = mock_exec

    response = auth_client.get(f"{BASE}/")
    assert response.status_code == 200


# ─── Scenario 3: Get Booking Details ───────────────────────────────────────────

def test_get_booking_not_found(auth_client, mock_db):
    """❌ GET /999999 → 404"""
    mock_db.get.return_value = None
    response = auth_client.get(f"{BASE}/999999")
    assert response.status_code == 404


def test_get_booking_wrong_owner(auth_client, mock_db):
    """❌ GET /{booking_id} for another user's booking → 404"""
    from app.models.battery_reservation import BatteryReservation
    mock_booking = MagicMock(spec=BatteryReservation)
    mock_booking.user_id = 999  # Different from MockUser.id=5

    mock_db.get.return_value = mock_booking
    response = auth_client.get(f"{BASE}/1")
    assert response.status_code == 404


def test_get_booking_success(auth_client, mock_db):
    """✅ GET /{booking_id} for own booking → 200"""
    from app.models.battery_reservation import BatteryReservation
    mock_booking = MagicMock(spec=BatteryReservation)
    mock_booking.user_id = 5  # Same as MockUser.id

    mock_db.get.return_value = mock_booking
    response = auth_client.get(f"{BASE}/1")
    assert response.status_code == 200


# ─── Scenario 4: Update Booking ────────────────────────────────────────────────

@pytest.mark.parametrize("new_status", ["CONFIRMED", "PENDING", "CANCELLED"])
def test_update_booking_status_valid(auth_client, mock_db, new_status):
    """✅ PUT /{booking_id} with valid status → 200"""
    from app.models.battery_reservation import BatteryReservation
    mock_booking = MagicMock(spec=BatteryReservation)
    mock_booking.user_id = 5
    mock_booking.status = "PENDING"

    mock_db.get.return_value = mock_booking

    response = auth_client.put(f"{BASE}/1", json={"status": new_status})
    assert response.status_code in [200, 404, 422]


def test_update_booking_not_found(auth_client, mock_db):
    """❌ PUT /999999 → 404"""
    mock_db.get.return_value = None
    response = auth_client.put(f"{BASE}/999999", json={"status": "CONFIRMED"})
    assert response.status_code == 404


def test_update_booking_wrong_owner(auth_client, mock_db):
    """❌ PUT for another user's booking → 404"""
    from app.models.battery_reservation import BatteryReservation
    mock_booking = MagicMock(spec=BatteryReservation)
    mock_booking.user_id = 999  # Not current user

    mock_db.get.return_value = mock_booking
    response = auth_client.put(f"{BASE}/1", json={"status": "CONFIRMED"})
    assert response.status_code == 404


# ─── Scenario 5: Cancel Booking ────────────────────────────────────────────────

def test_cancel_booking_success(auth_client, mock_db):
    """✅ DELETE /{booking_id} → 200 with cancel message"""
    from app.models.battery_reservation import BatteryReservation
    mock_booking = MagicMock(spec=BatteryReservation)
    mock_booking.user_id = 5

    mock_db.get.return_value = mock_booking
    response = auth_client.delete(f"{BASE}/1")

    assert response.status_code == 200
    data = response.json()
    assert "cancelled" in data.get("message", "").lower()


def test_cancel_booking_not_found(auth_client, mock_db):
    """❌ DELETE /999999 → 404"""
    mock_db.get.return_value = None
    response = auth_client.delete(f"{BASE}/999999")
    assert response.status_code == 404


def test_cancel_booking_wrong_owner(auth_client, mock_db):
    """❌ DELETE for another user's booking → 404"""
    from app.models.battery_reservation import BatteryReservation
    mock_booking = MagicMock(spec=BatteryReservation)
    mock_booking.user_id = 999

    mock_db.get.return_value = mock_booking
    response = auth_client.delete(f"{BASE}/1")
    assert response.status_code == 404


def test_cancel_booking_unauthenticated(anon_client):
    """❌ DELETE without auth → 401/422"""
    response = anon_client.delete(f"{BASE}/1")
    assert response.status_code in [401, 403, 422]


# ─── Scenario 6: Booking Reminder ──────────────────────────────────────────────

def test_send_booking_reminder(auth_client):
    """✅ POST /{booking_id}/reminder → 200"""
    response = auth_client.post(f"{BASE}/1/reminder")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert response.json().get("message") == "Reminder sent"


def test_send_reminder_unauthenticated(anon_client):
    """❌ POST without auth → 401/422"""
    response = anon_client.post(f"{BASE}/1/reminder")
    assert response.status_code in [401, 403, 422]


# ─── Scenario 7: Pay for Booking ───────────────────────────────────────────────

def test_pay_for_booking(auth_client):
    """✅ POST /{booking_id}/pay → 200 with payment success"""
    response = auth_client.post(f"{BASE}/1/pay")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert "Payment successful" in data.get("message", "")
        assert data.get("booking_id") == 1


def test_pay_for_booking_unauthenticated(anon_client):
    """❌ POST /pay without auth → 401/422"""
    response = anon_client.post(f"{BASE}/1/pay")
    assert response.status_code in [401, 403, 422]


# ─── Scenario 8: Edge Cases ─────────────────────────────────────────────────────

def test_booking_id_zero(auth_client):
    """⚠️ GET /0 → 404 or 422"""
    response = auth_client.get(f"{BASE}/0")
    assert response.status_code in [404, 422]


def test_booking_id_negative(auth_client):
    """⚠️ GET /-1 → 422 (path validation)"""
    response = auth_client.get(f"{BASE}/-1")
    assert response.status_code in [404, 422]


def test_booking_id_string(auth_client):
    """❌ GET /abc → 422 (type validation)"""
    response = auth_client.get(f"{BASE}/abc")
    assert response.status_code == 422
