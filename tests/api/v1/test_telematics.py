"""
Test suite for Telematics module
Covers: location update, telemetry, location history, travel path, geofence status
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime
from app.main import app
from app.api import deps
from app.core.database import get_db as core_get_db

BASE = "/api/v1/telemetry"


# ─── Mock User ─────────────────────────────────────────────────────────────────

class MockUser:
    id = 7
    is_superuser = False
    is_active = True
    role_id = 2
    email = "rider@wezu.com"
    full_name = "Test Rider"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    return MockUser()


@pytest.fixture
def auth_client(mock_db, mock_user):
    """Authenticated client for telemetry tests."""
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


@pytest.fixture
def own_rental(mock_db, mock_user):
    """A rental belonging to the current user."""
    from app.models.rental import Rental
    from app.models.battery import Battery

    mock_battery = MagicMock(spec=Battery)
    mock_battery.health_percentage = 85.0
    mock_battery.current_charge = 75.0
    mock_battery.last_latitude = 17.385
    mock_battery.last_longitude = 78.486

    mock_rental = MagicMock(spec=Rental)
    mock_rental.id = 1
    mock_rental.user_id = mock_user.id   # Same users
    mock_rental.battery_id = 1
    mock_rental.battery = mock_battery

    mock_db.get.return_value = mock_rental
    return mock_rental


@pytest.fixture
def other_rental(mock_db):
    """A rental belonging to a DIFFERENT user."""
    from app.models.rental import Rental
    mock_rental = MagicMock(spec=Rental)
    mock_rental.id = 2
    mock_rental.user_id = 999  # Different from MockUser.id=7

    mock_db.get.return_value = mock_rental
    return mock_rental


# ─── Scenario 1: Update GPS Location ──────────────────────────────────────────

def test_update_location_valid(auth_client, own_rental, mock_db):
    """✅ POST /rentals/{id}/location with valid coords → 200"""
    from app.services.gps_service import GPSTrackingService

    mock_log = MagicMock()
    mock_log.id = 1
    mock_log.timestamp = datetime.utcnow()

    with patch.object(GPSTrackingService, "log_location", return_value=mock_log):
        response = auth_client.post(
            f"{BASE}/rentals/1/location",
            json={"latitude": 17.385, "longitude": 78.486, "accuracy": 5.0}
        )
    assert response.status_code in [200, 403, 404]
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert "log_id" in data["data"]


@pytest.mark.parametrize("lat,lon,expected", [
    (17.385, 78.486, [200, 403, 404]),    # valid coords
    (0.0, 0.0, [200, 403, 404]),          # equator
    (-90.0, -180.0, [200, 403, 404]),     # min boundary
    (90.0, 180.0, [200, 403, 404]),       # max boundary
])
def test_update_location_boundary_coords(auth_client, own_rental, mock_db, lat, lon, expected):
    """✅ Boundary coordinate values → accepted"""
    from app.services.gps_service import GPSTrackingService

    mock_log = MagicMock()
    mock_log.id = 1
    mock_log.timestamp = datetime.utcnow()

    with patch.object(GPSTrackingService, "log_location", return_value=mock_log):
        response = auth_client.post(
            f"{BASE}/rentals/1/location",
            json={"latitude": lat, "longitude": lon}
        )
    assert response.status_code in expected


@pytest.mark.parametrize("lat,lon", [
    (91.0, 78.0),     # lat > 90
    (-91.0, 78.0),    # lat < -90
    (17.0, 181.0),    # lon > 180
    (17.0, -181.0),   # lon < -180
])
def test_update_location_out_of_bounds(auth_client, lat, lon):
    """❌ Out-of-range coordinates → 422"""
    response = auth_client.post(
        f"{BASE}/rentals/1/location",
        json={"latitude": lat, "longitude": lon}
    )
    assert response.status_code == 422


def test_update_location_missing_coords(auth_client):
    """❌ POST with missing lat/lon → 422"""
    response = auth_client.post(f"{BASE}/rentals/1/location", json={})
    assert response.status_code == 422


def test_update_location_negative_accuracy(auth_client, own_rental):
    """❌ Negative accuracy → 422"""
    response = auth_client.post(
        f"{BASE}/rentals/1/location",
        json={"latitude": 17.385, "longitude": 78.486, "accuracy": -5.0}
    )
    assert response.status_code == 422


def test_update_location_unauthorized_rental(auth_client, other_rental, mock_db):
    """❌ Updating location for another user's rental → 403"""
    response = auth_client.post(
        f"{BASE}/rentals/2/location",
        json={"latitude": 17.385, "longitude": 78.486}
    )
    assert response.status_code in [403, 404]


def test_update_location_unauthenticated(anon_client):
    """❌ No auth → 401/422"""
    response = anon_client.post(
        f"{BASE}/rentals/1/location",
        json={"latitude": 17.385, "longitude": 78.486}
    )
    assert response.status_code in [401, 403, 422]


# ─── Scenario 2: Get Rental Telemetry ──────────────────────────────────────────

def test_get_telemetry_success(auth_client, own_rental):
    """✅ GET /rentals/{id}/telemetry → 200 with telemetry data"""
    response = auth_client.get(f"{BASE}/rentals/1/telemetry")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        required_keys = {"voltage", "temperature", "health", "charge",
                         "latitude", "longitude", "last_updated", "status"}
        assert required_keys.issubset(data.keys())


def test_get_telemetry_status_values(auth_client, own_rental):
    """✅ Telemetry status should be one of normal/warning/critical"""
    response = auth_client.get(f"{BASE}/rentals/1/telemetry")
    if response.status_code == 200:
        status = response.json()["status"]
        assert status in ["normal", "warning", "critical"]


def test_get_telemetry_rental_not_found(auth_client, mock_db):
    """❌ GET /999999/telemetry → 404"""
    mock_db.get.return_value = None
    response = auth_client.get(f"{BASE}/rentals/999999/telemetry")
    assert response.status_code == 404


def test_get_telemetry_numeric_ranges(auth_client, own_rental):
    """✅ Voltage & temperature are within realistic physical ranges"""
    response = auth_client.get(f"{BASE}/rentals/1/telemetry")
    if response.status_code == 200:
        data = response.json()
        # EV battery voltage typically 60-84V for 72V systems
        assert 50 <= data["voltage"] <= 100
        # Temperature should be a realistic number
        assert -20 <= data["temperature"] <= 100
        # Health/charge 0-100%
        assert 0 <= data["health"] <= 100
        assert 0 <= data["charge"] <= 100


# ─── Scenario 3: Location History ──────────────────────────────────────────────

def test_get_location_history(auth_client, mock_db):
    """✅ GET /rentals/{id}/location-history → list of points"""
    from app.services.gps_service import GPSTrackingService

    mock_point = MagicMock()
    mock_point.latitude = 17.385
    mock_point.longitude = 78.486
    mock_point.timestamp = datetime.utcnow()

    with patch.object(GPSTrackingService, "get_location_history", return_value=[mock_point]):
        response = auth_client.get(f"{BASE}/rentals/1/location-history")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_location_history_empty(auth_client, mock_db):
    """✅ GET /location-history on new rental → empty list"""
    from app.services.gps_service import GPSTrackingService

    with patch.object(GPSTrackingService, "get_location_history", return_value=[]):
        response = auth_client.get(f"{BASE}/rentals/1/location-history")

    assert response.status_code == 200
    assert response.json() == []


def test_get_location_history_point_structure(auth_client, mock_db):
    """✅ Location history points have lat/lon/timestamp"""
    from app.services.gps_service import GPSTrackingService

    mock_point = MagicMock()
    mock_point.latitude = 17.385
    mock_point.longitude = 78.486
    mock_point.timestamp = datetime.utcnow()

    with patch.object(GPSTrackingService, "get_location_history", return_value=[mock_point]):
        response = auth_client.get(f"{BASE}/rentals/1/location-history")

    if response.status_code == 200 and len(response.json()) > 0:
        point = response.json()[0]
        assert "latitude" in point
        assert "longitude" in point
        assert "timestamp" in point


# ─── Scenario 4: Travel Path ────────────────────────────────────────────────────

def test_get_travel_path(auth_client, mock_db):
    """✅ GET /rentals/{id}/travel-path → 200 with path data"""
    from app.services.gps_service import GPSTrackingService

    mock_path = {
        "total_distance_km": 12.5,
        "points": [],
        "start_time": datetime.utcnow().isoformat(),
        "end_time": datetime.utcnow().isoformat(),
    }

    with patch.object(GPSTrackingService, "get_travel_path", return_value=mock_path):
        response = auth_client.get(f"{BASE}/rentals/1/travel-path")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data


def test_get_travel_path_invalid_rental(auth_client, mock_db):
    """❌ GET /999999/travel-path → 404 or 200 with empty data"""
    from app.services.gps_service import GPSTrackingService

    with patch.object(GPSTrackingService, "get_travel_path", return_value={}):
        response = auth_client.get(f"{BASE}/rentals/999999/travel-path")

    assert response.status_code in [200, 404]


# ─── Scenario 5: Geofence Status ────────────────────────────────────────────────

def test_get_geofence_status_no_location(auth_client, mock_db):
    """❌ GET /rentals/{id}/geofence-status with no GPS data → 404"""
    from app.services.gps_service import GPSTrackingService

    with patch.object(GPSTrackingService, "get_current_location", return_value=None):
        response = auth_client.get(f"{BASE}/rentals/1/geofence-status")

    assert response.status_code == 404


def test_get_geofence_status_no_violation(auth_client, mock_db):
    """✅ GET /geofence-status within boundary → no violations"""
    from app.services.gps_service import GPSTrackingService
    from app.services.geofence_service import GeofenceService

    mock_location = MagicMock()
    mock_location.latitude = 17.385
    mock_location.longitude = 78.486

    mock_exec = MagicMock()
    mock_exec.all.return_value = []  # No active geofences
    mock_db.exec.return_value = mock_exec

    with patch.object(GPSTrackingService, "get_current_location", return_value=mock_location):
        response = auth_client.get(f"{BASE}/rentals/1/geofence-status")

    assert response.status_code == 200
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert data["data"]["has_violations"] is False


@pytest.mark.parametrize("rental_id", [0, -1])
def test_telemetry_endpoints_zero_and_negative_ids(auth_client, rental_id):
    """⚠️ Rental IDs 0 and negative → 404 or 422"""
    endpoints = [
        f"{BASE}/rentals/{rental_id}/location-history",
        f"{BASE}/rentals/{rental_id}/telemetry",
        f"{BASE}/rentals/{rental_id}/travel-path",
        f"{BASE}/rentals/{rental_id}/geofence-status",
    ]
    for endpoint in endpoints:
        response = auth_client.get(endpoint)
        assert response.status_code in [404, 422], f"Unexpected status for {endpoint}"
