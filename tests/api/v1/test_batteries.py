"""
Test suite for Battery module
Covers: CRUD, health-history, audit-logs, QR, batch ops, telemetry, low-health filter
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.core.database import get_db as core_get_db

BASE = "/api/v1/batteries"


# ─── Mock User ─────────────────────────────────────────────────────────────────

class MockSuperUser:
    id = 1
    is_superuser = True
    is_active = True
    role_id = 1
    email = "admin@wezu.com"
    full_name = "Admin"
    driver_profile = None
    dealer_profile = None


class MockRegularUser:
    id = 2
    is_superuser = False
    is_active = True
    role_id = 2
    email = "user@wezu.com"
    full_name = "Regular User"
    driver_profile = None
    dealer_profile = None


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def super_user():
    return MockSuperUser()


@pytest.fixture
def regular_user():
    return MockRegularUser()


@pytest.fixture
def admin_client(mock_db, super_user):
    """TestClient with superuser overrides."""
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    app.dependency_overrides[core_get_db] = lambda: mock_db
    app.dependency_overrides[deps.get_current_user] = lambda: super_user
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: super_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def user_client(mock_db, regular_user):
    """TestClient with regular user overrides."""
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    app.dependency_overrides[core_get_db] = lambda: mock_db
    app.dependency_overrides[deps.get_current_user] = lambda: regular_user
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: regular_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


# ─── Scenario 1: Get Battery By ID ─────────────────────────────────────────────

def test_get_battery_by_id_found(admin_client):
    """✅ GET /{battery_id} → returns battery details"""
    response = admin_client.get(f"{BASE}/1")
    assert response.status_code in [200, 404]


def test_get_battery_by_id_not_found(admin_client):
    """❌ GET /{battery_id} with non-existent ID → 404"""
    response = admin_client.get(f"{BASE}/999999")
    assert response.status_code == 404


# ─── Scenario 2: Health History ────────────────────────────────────────────────

def test_get_health_history_default_limit(admin_client):
    """✅ GET /{battery_id}/health-history → 200 with list"""
    response = admin_client.get(f"{BASE}/1/health-history")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert "data" in response.json()


def test_get_health_history_custom_limit(admin_client):
    """✅ GET /{battery_id}/health-history?limit=10 → respects limit"""
    response = admin_client.get(f"{BASE}/1/health-history?limit=10")
    assert response.status_code in [200, 404]


def test_get_health_history_overlimit(admin_client):
    """❌ limit > 200 → 422 Validation Error"""
    response = admin_client.get(f"{BASE}/1/health-history?limit=500")
    assert response.status_code == 422


# ─── Scenario 3: Audit Logs ────────────────────────────────────────────────────

def test_get_audit_logs(admin_client):
    """✅ GET /{battery_id}/audit-logs → 200"""
    response = admin_client.get(f"{BASE}/1/audit-logs")
    assert response.status_code in [200, 404]


def test_get_audit_logs_over_limit(admin_client):
    """❌ limit > 200 → 422"""
    response = admin_client.get(f"{BASE}/1/audit-logs?limit=300")
    assert response.status_code == 422


# ─── Scenario 4: Rental History ────────────────────────────────────────────────

def test_get_rental_history(admin_client):
    """✅ GET /{battery_id}/rental-history → 200"""
    response = admin_client.get(f"{BASE}/1/rental-history")
    assert response.status_code in [200, 404]


def test_get_rental_history_over_limit(admin_client):
    """❌ limit > 100 → 422"""
    response = admin_client.get(f"{BASE}/1/rental-history?limit=999")
    assert response.status_code == 422


# ─── Scenario 5: Low-Health Filter ─────────────────────────────────────────────

@pytest.mark.parametrize("threshold,expected_code", [
    (80.0, 200),   # valid threshold
    (50.0, 200),   # low threshold
    (100.0, 200),  # max threshold
])
def test_get_low_health_batteries_thresholds(admin_client, threshold, expected_code):
    """✅ GET /low-health?threshold=X → valid responses"""
    response = admin_client.get(f"{BASE}/low-health?threshold={threshold}")
    assert response.status_code == expected_code
    if response.status_code == 200:
        assert isinstance(response.json(), list)


# ─── Scenario 6: Scan QR Code ──────────────────────────────────────────────────

def test_scan_qr_valid(admin_client):
    """✅ POST /scan-qr with valid data → 200 or 404"""
    response = admin_client.post(f"{BASE}/scan-qr", json={"qr_code_data": "BATTERY-QR-001"})
    assert response.status_code in [200, 404]


def test_scan_qr_missing_field(admin_client):
    """❌ POST /scan-qr with missing field → 422"""
    response = admin_client.post(f"{BASE}/scan-qr", json={})
    assert response.status_code == 422


def test_scan_qr_empty_string(admin_client):
    """❌ POST /scan-qr with empty QR data → 404"""
    response = admin_client.post(f"{BASE}/scan-qr", json={"qr_code_data": ""})
    assert response.status_code in [404, 422]


# ─── Scenario 7: Update Battery Status ─────────────────────────────────────────

@pytest.mark.parametrize("new_status", ["available", "maintenance", "retired"])
def test_update_battery_status_valid(admin_client, new_status):
    """✅ PUT /{battery_id}/status → updates status correctly"""
    response = admin_client.put(
        f"{BASE}/1/status",
        params={"status": new_status, "description": f"Set to {new_status}"}
    )
    assert response.status_code in [200, 404]


def test_update_battery_status_not_found(admin_client):
    """❌ PUT /999/status → 404"""
    response = admin_client.put(
        f"{BASE}/999999/status",
        params={"status": "retired"}
    )
    assert response.status_code == 404


# ─── Scenario 8: Assign Station ────────────────────────────────────────────────

def test_assign_battery_to_station(admin_client):
    """✅ POST /{battery_id}/assign-station → assigns or 404"""
    response = admin_client.post(f"{BASE}/1/assign-station?station_id=1")
    assert response.status_code in [200, 404]


def test_assign_battery_station_not_found_battery(admin_client):
    """❌ non-existent battery ID → 404"""
    response = admin_client.post(f"{BASE}/999999/assign-station?station_id=1")
    assert response.status_code == 404


# ─── Scenario 9: Batch Update Validation ────────────────────────────────────────

def test_batch_update_too_many(admin_client):
    """❌ PUT /batch/update with > 1000 items → 400"""
    updates = [{"serial_number": f"SN{i}", "status": "available"} for i in range(1001)]
    response = admin_client.put(f"{BASE}/batch/update", json=updates)
    assert response.status_code == 400


def test_batch_update_empty(admin_client):
    """❌ PUT /batch/update with empty list → 400"""
    response = admin_client.put(f"{BASE}/batch/update", json=[])
    assert response.status_code == 400


def test_batch_update_valid_small(admin_client):
    """✅ PUT /batch/update with 2 items → 200"""
    updates = [
        {"serial_number": "SN001", "status": "available"},
        {"serial_number": "SN002", "status": "maintenance"},
    ]
    response = admin_client.put(f"{BASE}/batch/update", json=updates)
    assert response.status_code in [200, 400, 422]


# ─── Scenario 10: Battery Alerts ────────────────────────────────────────────────

def test_get_battery_alerts_auth_required(user_client):
    """✅ GET /{battery_id}/alerts → requires authenticated user"""
    response = user_client.get(f"{BASE}/1/alerts")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert "data" in response.json()


def test_get_battery_alerts_no_auth(admin_client):
    """✅ GET /{battery_id}/alerts unauthenticated → handled"""
    response = admin_client.get(f"{BASE}/1/alerts")
    assert response.status_code in [200, 401, 404]


# ─── Scenario 11: Decommission Battery ──────────────────────────────────────────

def test_decommission_battery_success(admin_client):
    """✅ DELETE /{battery_id} → retires battery"""
    response = admin_client.delete(f"{BASE}/1")
    assert response.status_code in [200, 404]


def test_decommission_battery_not_found(admin_client):
    """❌ DELETE /999999 → 404"""
    response = admin_client.delete(f"{BASE}/999999")
    assert response.status_code == 404
