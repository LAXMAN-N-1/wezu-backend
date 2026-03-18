import pytest

def test_get_nearby_stations_no_filters(client):
    response = client.get("/api/v1/customer/stations/nearby?lat=12.9716&lon=77.5946&radius=10.0")
    if response.status_code == 404:
        # Fallback if mounted without customer prefix
        response = client.get("/api/v1/stations/nearby?lat=12.9716&lon=77.5946&radius=10.0")

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)

def test_get_nearby_stations_with_filters(client):
    response = client.get(
        "/api/v1/customer/stations/nearby",
        params={
            "lat": 12.9716,
            "lon": 77.5946,
            "min_rating": 4.5,
            "battery_type": "lithium_ion",
            "capacity_min": 1000,
            "price_max": 20.0,
            "availability": True
        }
    )
    if response.status_code == 404:
        response = client.get(
            "/api/v1/stations/nearby",
            params={
                "lat": 12.9716,
                "lon": 77.5946,
                "min_rating": 4.5,
                "battery_type": "lithium_ion",
                "capacity_min": 1000,
                "price_max": 20.0,
                "availability": True
            }
        )
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)

def test_get_nearby_stations_invalid_rating(client):
    response = client.get(
        "/api/v1/customer/stations/nearby",
        params={
            "lat": 12.9716,
            "lon": 77.5946,
            "min_rating": 10.0
        }
    )
    if response.status_code == 404:
        response = client.get(
            "/api/v1/stations/nearby",
            params={
                "lat": 12.9716,
                "lon": 77.5946,
                "min_rating": 10.0
            }
        )
    assert response.status_code == 422, response.text
    assert "detail" in response.json()

def test_get_nearby_stations_invalid_price_range(client):
    response = client.get(
        "/api/v1/customer/stations/nearby",
        params={
            "lat": 12.9716,
            "lon": 77.5946,
            "price_min": 100.0,
            "price_max": 50.0
        }
    )
    if response.status_code == 404:
        response = client.get(
            "/api/v1/stations/nearby",
            params={
                "lat": 12.9716,
                "lon": 77.5946,
                "price_min": 100.0,
                "price_max": 50.0
            }
        )
    assert response.status_code == 422, response.text
    assert "detail" in response.json()
