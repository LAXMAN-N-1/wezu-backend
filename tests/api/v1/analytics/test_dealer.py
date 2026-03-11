import pytest
from fastapi.testclient import TestClient
from app.core.config import settings

def test_dealer_overview_success(client: TestClient, mock_admin_token_headers: dict[str, str]):
    """
    Test dealer analytics. Currently bypassing standard dealer auth checks
    using an admin token, testing structural consistency.
    """
    response = client.get(
        f"{settings.API_V1_STR}/analytics/dealer/overview",
        headers=mock_admin_token_headers
    )
    
    assert response.status_code == 200, response.text
    data = response.json()
    
    assert "sales_analytics" in data
    assert "rental_analytics" in data
    assert "inventory_analytics" in data
    assert "revenue_analytics" in data
    assert "station_analytics" in data
    
    inv = data["inventory_analytics"]
    assert "total_batteries" in inv
    assert "available_batteries" in inv
    assert "batteries_rented" in inv
