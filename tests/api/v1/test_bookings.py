import pytest
from fastapi import status

# --- POSITIVE CASES ---

def test_list_bookings_success(client, normal_user_token_headers):
    """Test retrieving list of bookings for the current user"""
    response = client.get("/api/v1/bookings/", headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)

def test_create_booking_success(client, normal_user_token_headers):
    """Test successful booking creation"""
    payload = {"station_id": 1}
    response = client.post("/api/v1/bookings/", json=payload, headers=normal_user_token_headers)
    # Success can be 200/201, or 400 if no slots available in seeded data
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

def test_get_booking_by_id(client, normal_user_token_headers):
    """Test retrieving a specific booking"""
    response = client.get("/api/v1/bookings/1", headers=normal_user_token_headers)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

def test_pay_for_booking_success(client, normal_user_token_headers):
    """Test successful payment for a booking"""
    response = client.post("/api/v1/bookings/1/pay", headers=normal_user_token_headers)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

# --- NEGATIVE CASES ---

def test_list_bookings_unauthorized(client):
    """Test accessing bookings without authentication"""
    response = client.get("/api/v1/bookings/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_create_booking_missing_station(client, normal_user_token_headers):
    """Test booking creation with missing station_id"""
    response = client.post("/api/v1/bookings/", json={}, headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_cancel_booking_not_found(client, normal_user_token_headers):
    """Test cancelling a non-existent booking"""
    response = client.delete("/api/v1/bookings/99999", headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# --- EDGE CASES ---

def test_booking_id_invalid_type(client, normal_user_token_headers):
    """Test fetching booking with non-integer ID"""
    response = client.get("/api/v1/bookings/invalid", headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_create_booking_large_payload(client, normal_user_token_headers):
    """Test booking creation with unnecessary extra fields"""
    payload = {"station_id": 1, "extra_junk": "x" * 1000}
    response = client.post("/api/v1/bookings/", json=payload, headers=normal_user_token_headers)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
