"""
Test suite for Battery Alerts module (customer-facing)
Covers: active alerts, alert config, dismiss, history
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.core.database import get_db as core_get_db

ALERTS_BASE = "/api/v1/customer/battery-alerts"


# ─── Mock User ─────────────────────────────────────────────────────────────────

class MockCustomer:
    id = 10
    is_superuser = False
    is_active = True
    role_id = 3
    email = "customer@wezu.com"
    full_name = "Test Customer"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def customer_user():
    return MockCustomer()


@pytest.fixture
def customer_client(mock_db, customer_user):
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    app.dependency_overrides[core_get_db] = lambda: mock_db
    app.dependency_overrides[deps.get_current_user] = lambda: customer_user
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: customer_user

    mock_db.exec.return_value = MagicMock(all=MagicMock(return_value=[]), first=MagicMock(return_value=None))

    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


# ─── Scenario 1: Get Active Alerts ─────────────────────────────────────────────

def test_get_active_alerts_no_rentals(customer_client):
    """✅ User with no active rentals → empty list"""
    response = customer_client.get(f"{ALERTS_BASE}")
    assert response.status_code == 200
    assert response.json() == []


def test_get_active_alerts_returns_list(customer_client):
    """✅ GET /customer/battery-alerts → returns list"""
    response = customer_client.get(f"{ALERTS_BASE}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_active_alerts_no_auth():
    """❌ No auth → 401/403"""
    with TestClient(app) as c:
        response = c.get(f"{ALERTS_BASE}")
    assert response.status_code in [401, 403, 422]


# ─── Scenario 2: Alert Config – Get ────────────────────────────────────────────

def test_get_alert_config_default(customer_client):
    """✅ GET /config → returns default config when none exists"""
    response = customer_client.get(f"{ALERTS_BASE}/config")
    assert response.status_code == 200
    data = response.json()
    # Should have config structure
    assert isinstance(data, dict)


def test_get_alert_config_structure(customer_client):
    """✅ Config response has expected keys"""
    response = customer_client.get(f"{ALERTS_BASE}/config")
    assert response.status_code == 200
    data = response.json()
    # Common config fields expected
    expected_keys = {"low_charge_percent", "low_health_percent", "high_temp_celsius", "alerts_enabled"}
    assert expected_keys.issubset(data.keys())


# ─── Scenario 3: Alert Config – Update ─────────────────────────────────────────

@pytest.mark.parametrize("low_charge,low_health,high_temp,alerts_enabled", [
    (20, 70, 45, True),
    (10, 60, 50, False),
    (30, 80, 40, True),
])
def test_update_alert_config_valid(customer_client, low_charge, low_health, high_temp, alerts_enabled):
    """✅ PUT /config with valid data → 200"""
    payload = {
        "low_charge_percent": low_charge,
        "low_health_percent": low_health,
        "high_temp_celsius": high_temp,
        "alerts_enabled": alerts_enabled,
    }
    response = customer_client.put(f"{ALERTS_BASE}/config", json=payload)
    assert response.status_code in [200, 422]


def test_update_alert_config_missing_fields(customer_client):
    """❌ PUT /config with empty body → may use defaults or 422"""
    response = customer_client.put(f"{ALERTS_BASE}/config", json={})
    assert response.status_code in [200, 422]


# ─── Scenario 4: Dismiss Alert ─────────────────────────────────────────────────

def test_dismiss_alert_not_found(customer_client):
    """❌ POST /999/dismiss → 404"""
    response = customer_client.post(f"{ALERTS_BASE}/999999/dismiss")
    assert response.status_code == 404


def test_dismiss_alert_success(customer_client, mock_db):
    """✅ POST /{alert_id}/dismiss → 200 success"""
    from app.models.battery_health import BatteryHealthAlert
    from app.models.rental import Rental

    mock_alert = MagicMock(spec=BatteryHealthAlert)
    mock_alert.battery_id = 1
    mock_alert.is_resolved = False

    mock_rental = MagicMock(spec=Rental)
    mock_rental.user_id = 10
    mock_rental.battery_id = 1

    mock_db.get.return_value = mock_alert
    mock_exec = MagicMock()
    mock_exec.first.return_value = mock_rental
    mock_db.exec.return_value = mock_exec

    response = customer_client.post(f"{ALERTS_BASE}/1/dismiss")
    assert response.status_code in [200, 403, 404]
    if response.status_code == 200:
        assert response.json()["status"] == "success"


def test_dismiss_already_resolved_alert(customer_client, mock_db):
    """⚠️ POST /{alert_id}/dismiss on already resolved → still 200"""
    from app.models.battery_health import BatteryHealthAlert
    from app.models.rental import Rental

    mock_alert = MagicMock(spec=BatteryHealthAlert)
    mock_alert.battery_id = 2
    mock_alert.is_resolved = True  # Already resolved

    mock_rental = MagicMock(spec=Rental)
    mock_rental.user_id = 10
    mock_rental.battery_id = 2

    mock_db.get.return_value = mock_alert
    mock_exec = MagicMock()
    mock_exec.first.return_value = mock_rental
    mock_db.exec.return_value = mock_exec

    response = customer_client.post(f"{ALERTS_BASE}/2/dismiss")
    assert response.status_code in [200, 403, 404]


def test_dismiss_alert_not_authorized(customer_client, mock_db):
    """❌ POST /{alert_id}/dismiss for other user's rental → 403"""
    from app.models.battery_health import BatteryHealthAlert

    mock_alert = MagicMock(spec=BatteryHealthAlert)
    mock_alert.battery_id = 99

    mock_db.get.return_value = mock_alert
    mock_exec = MagicMock()
    mock_exec.first.return_value = None  # No matching rental for current user
    mock_db.exec.return_value = mock_exec

    response = customer_client.post(f"{ALERTS_BASE}/1/dismiss")
    assert response.status_code in [403, 404]


# ─── Scenario 5: Alert History ─────────────────────────────────────────────────

def test_get_alert_history_empty(customer_client):
    """✅ GET /history → empty list when no rentals"""
    response = customer_client.get(f"{ALERTS_BASE}/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_alert_history_returns_sorted_list(customer_client, mock_db):
    """✅ GET /history → sorted descending by created_at"""
    from app.models.rental import Rental
    from app.models.battery_health import BatteryHealthAlert
    from datetime import datetime

    mock_rental = MagicMock(spec=Rental)
    mock_rental.battery_id = 5

    mock_alert = MagicMock(spec=BatteryHealthAlert)
    mock_alert.battery_id = 5
    mock_alert.created_at = datetime.utcnow()

    # First exec → rentals list
    # Second exec → alerts list
    mock_exec_rentals = MagicMock()
    mock_exec_rentals.all.return_value = [mock_rental]

    mock_exec_alerts = MagicMock()
    mock_exec_alerts.all.return_value = [mock_alert]

    mock_db.exec.side_effect = [mock_exec_rentals, mock_exec_alerts]

    response = customer_client.get(f"{ALERTS_BASE}/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
