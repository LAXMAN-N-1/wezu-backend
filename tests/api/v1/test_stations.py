import pytest
from fastapi import status

# --- POSITIVE CASES ---

def test_read_stations_as_admin(client, admin_token_headers):
    """Test retrieving stations as an admin"""
    response = client.get("/api/v1/stations/", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)

def test_create_station_success(client, admin_token_headers):
    """Test successful station creation by admin"""
    payload = {
        "name": "Admin Super Station",
        "address": "123 Admin Way",
        "latitude": 12.97,
        "longitude": 77.59,
        "station_type": "automated",
        "total_slots": 20
    }
    response = client.post("/api/v1/stations/", json=payload, headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Admin Super Station"
    return data["id"]

def test_read_station_by_id(client, admin_token_headers):
    """Test retrieving a specific station"""
    # Create one first
    payload = {"name": "Find Me", "latitude": 0, "longitude": 0, "total_slots": 5}
    create_res = client.post("/api/v1/stations/", json=payload, headers=admin_token_headers)
    station_id = create_res.json()["id"]
    
    response = client.get(f"/api/v1/stations/{station_id}", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Find Me"

def test_search_nearby_stations(client):
    """Test nearby search (public endpoint)"""
    response = client.get(
        "/api/v1/stations/nearby",
        params={"lat": 12.97, "lon": 77.59, "radius": 10.0}
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)

# --- NEGATIVE CASES ---

def test_create_station_unauthorized(client, normal_user_token_headers):
    """Test that a normal user cannot create a station"""
    payload = {"name": "Illegal Station", "latitude": 0, "longitude": 0}
    response = client.post("/api/v1/stations/", json=payload, headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_get_station_not_found(client, admin_token_headers):
    """Test retrieving a non-existent station"""
    response = client.get("/api/v1/stations/99999", headers=admin_token_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_update_station_invalid_data(client, admin_token_headers):
    """Test updating station with invalid latitude"""
    payload = {"latitude": 1000} # Invalid lat
    response = client.put("/api/v1/stations/1", json=payload, headers=admin_token_headers)
    assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_404_NOT_FOUND]

# --- EDGE CASES ---

def test_search_nearby_extreme_coordinates(client):
    """Test nearby search with extreme lat/lon"""
    response = client.get(
        "/api/v1/stations/nearby",
        params={"lat": 90.0, "lon": 180.0}
    )
    assert response.status_code == status.HTTP_200_OK

def test_read_stations_large_limit(client, admin_token_headers):
    """Test pagination with a very large limit"""
    response = client.get("/api/v1/stations/?limit=10000", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK