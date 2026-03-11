import pytest
from fastapi.testclient import TestClient
from app.core.config import settings

def test_customer_overview_success(client: TestClient, mock_customer_token_headers: dict[str, str], session):
    """
    Test that a customer can successfully retrieve their own overview data.
    """
    response = client.get(
        f"{settings.API_V1_STR}/analytics/customer/overview?period=30d",
        headers=mock_customer_token_headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    
    assert "personal_overview" in data
    assert "spending_analytics" in data
    assert "usage_analytics" in data
    
    # Assert specific fields and their mock baseline shapes
    personal = data["personal_overview"]
    assert "membership_level" in personal
    # Our fallback logic sets it to Bronze when no row exists
    assert personal["membership_level"] == "Bronze"

def test_customer_overview_unauthorized(client: TestClient):
    """
    Test that an unauthenticated user gets rejected.
    """
    response = client.get(f"{settings.API_V1_STR}/analytics/customer/overview")
    assert response.status_code == 401
