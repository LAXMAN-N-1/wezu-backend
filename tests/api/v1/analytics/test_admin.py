import pytest
from fastapi.testclient import TestClient
from app.core.config import settings

def test_admin_overview_success(client: TestClient, mock_admin_token_headers: dict[str, str]):
    """
    Test that an admin user can successfully fetch the admin analytics overview
    and the response structure conforms to the schema.
    """
    response = client.get(
        f"{settings.API_V1_STR}/analytics/admin/overview?period=7d",
        headers=mock_admin_token_headers,
    )
    
    # Due to RBAC setup complexity in tests, if it returns 403, we might need to adjust roles
    # For now we assume is_superuser=True works or the role header is enough
    assert response.status_code == 200, response.text
    data = response.json()
    
    # Assert main structure categories exist
    assert "platform_overview" in data
    assert "rental_analytics" in data
    assert "revenue_analytics" in data
    assert "battery_fleet_analytics" in data
    assert "station_analytics" in data
    
    # Check platform overview structure matches KpiCard shapes (or basic proxy)
    platform = data["platform_overview"]
    assert "total_users" in platform
    assert "total_dealers" in platform
    
def test_admin_overview_unauthorized(client: TestClient, mock_customer_token_headers: dict[str, str]):
    """
    Test that a regular customer user is denied access to admin analytics.
    """
    response = client.get(
        f"{settings.API_V1_STR}/analytics/admin/overview",
        headers=mock_customer_token_headers,
    )
    # Expected to be Forbidden (403) or Unauthorized (401) or Bad Request (400) depending on exact RBAC middleware behavior
    assert response.status_code in (400, 401, 403)

def test_admin_overview_no_auth(client: TestClient):
    """
    Test that unauthenticated requests are rejected.
    """
    response = client.get(f"{settings.API_V1_STR}/analytics/admin/overview")
    assert response.status_code == 401
