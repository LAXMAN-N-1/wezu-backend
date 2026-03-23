import pytest
from fastapi.testclient import TestClient
from app.core.config import settings

def test_logistics_overview_success(client: TestClient, mock_admin_token_headers: dict[str, str]):
    """
    Test that logistics overview returns properly.
    Uses an admin token to bypass RBAC on the endpoint for structural validation.
    """
    response = client.get(
        f"{settings.API_V1_STR}/analytics/logistics/overview?period=7d",
        headers=mock_admin_token_headers
    )
    
    assert response.status_code == 200, response.text
    data = response.json()
    
    assert "delivery_analytics" in data
    assert "route_analytics" in data
    assert "driver_analytics" in data
    assert "order_analytics" in data
    assert "reverse_logistics" in data
    
    # Check that our BatteryTransfer mapping logic outputs the right types
    deliv = data["delivery_analytics"]
    assert "total_deliveries" in deliv
    assert "pending_deliveries" in deliv
    assert isinstance(deliv["total_deliveries"], int)
