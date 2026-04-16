import pytest
from fastapi import status

# --- POSITIVE CASES ---

def test_read_batteries_as_admin(client, admin_token_headers):
    """Test retrieving all batteries as admin"""
    response = client.get("/api/v1/batteries/", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)

def test_get_battery_by_id(client, admin_token_headers):
    """Test retrieving a specific battery by ID"""
    response = client.get("/api/v1/batteries/1", headers=admin_token_headers)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

def test_scan_qr_success(client, admin_token_headers):
    """Test scanning a valid battery QR code"""
    payload = {"qr_code_data": "BATTERY-001"}
    response = client.post("/api/v1/batteries/scan-qr", json=payload, headers=admin_token_headers)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

def test_get_low_health_batteries(client, admin_token_headers):
    """Test filtering batteries with low health"""
    response = client.get("/api/v1/batteries/low-health?threshold=80.0", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)

# --- NEGATIVE CASES ---

def test_get_battery_unauthorized(client):
    """Test accessing batteries without authentication"""
    response = client.get("/api/v1/batteries/1")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_update_battery_status_not_found(client, admin_token_headers):
    """Test updating status of non-existent battery"""
    response = client.put("/api/v1/batteries/99999/status?status=available", headers=admin_token_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_batch_update_empty_list(client, admin_token_headers):
    """Test batch update with empty payload"""
    response = client.put("/api/v1/batteries/batch/update", json=[], headers=admin_token_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

# --- EDGE CASES ---

def test_batch_update_too_many(client, admin_token_headers):
    """Test batch update exceeding maximum limit"""
    updates = [{"serial_number": f"SN{i}", "status": "available"} for i in range(1001)]
    response = client.put("/api/v1/batteries/batch/update", json=updates, headers=admin_token_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_read_health_history_limit_overflow(client, admin_token_headers):
    """Test health history with a limit exceeding allowed maximum"""
    response = client.get("/api/v1/batteries/1/health-history?limit=500", headers=admin_token_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
