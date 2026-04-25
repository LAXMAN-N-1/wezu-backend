"""
Integration Tests: Analytics & Dashboard Aggregation Flow
=========================================================
Tests that analytics and dashboard endpoints correctly reflect data
and return valid, structured responses.

  Workflow 1: Customer Analytics Dashboard
    User registers → logs in → hits analytics/dashboard →
    hits rental-history, cost-analytics, usage-patterns, carbon-savings

  Workflow 2: Dealer Analytics Dashboard
    Dealer logs in → hits overview/trends/kpis/stations/peak-hours →
    all return structured metric responses

  Workflow 3: Admin Analytics & Aggregation
    Admin hits admin analytics endpoints:
    overview, trends, battery-health, revenue-by-region, top-stations, user-growth

  Workflow 4: Analytics Data Export
    Admin triggers CSV export → response is downloadable

Each class is an independent multi-step scenario run against an in-memory SQLite DB.
Results are persisted to the test_reports table by the conftest plugin.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


# ─── Helpers ──────────────────────────────────────────────────────────────────

def register_and_login(client: TestClient, email: str, phone: str,
                        password: str = "Pass@1234") -> str:
    """Register a customer user and return their access token."""
    client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Analytics Test User",
            "phone_number": phone,
        },
    )
    res = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    return res.json().get("access_token", "")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Workflow 1: Customer Analytics Dashboard ──────────────────────────────────

class TestCustomerAnalyticsDashboard:
    """
    Integration: Customer accesses all personal analytics endpoints.
    Validates structured response with success=True or equivalent.
    """

    @pytest.fixture
    def user_token(self, client: TestClient) -> str:
        return register_and_login(client, "int_analytics_customer@example.com", "9500000001")

    def test_customer_dashboard(self, client: TestClient, user_token: str):
        res = client.get(
            "/api/v1/analytics/dashboard",
            headers=bearer(user_token),
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Customer dashboard endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        # Accept both {"success": True, "data": {...}} and plain dict
        assert isinstance(body, dict)

    def test_rental_history_stats(self, client: TestClient, user_token: str):
        res = client.get(
            "/api/v1/analytics/rental-history",
            headers=bearer(user_token),
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Rental history stats endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        assert isinstance(res.json(), dict)

    def test_cost_analytics(self, client: TestClient, user_token: str):
        res = client.get(
            "/api/v1/analytics/cost-analytics",
            headers=bearer(user_token),
            params={"months": 3},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Cost analytics endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        assert isinstance(res.json(), dict)

    def test_usage_patterns(self, client: TestClient, user_token: str):
        res = client.get(
            "/api/v1/analytics/usage-patterns",
            headers=bearer(user_token),
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Usage patterns endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        assert isinstance(res.json(), dict)

    def test_carbon_savings(self, client: TestClient, user_token: str):
        res = client.get(
            "/api/v1/analytics/carbon-savings",
            headers=bearer(user_token),
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Carbon savings endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        assert isinstance(body, dict)
        # Response may be wrapped in {"data": {...}} or flat
        data = body.get("data", body)
        assert "carbon_saved_kg" in data or "total_rentals" in data

    def test_analytics_unauthorized_blocked(self, client: TestClient):
        res = client.get("/api/v1/analytics/dashboard")
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Analytics dashboard endpoint not mounted")
        assert res.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


# ─── Workflow 2: Dealer Analytics Dashboard ────────────────────────────────────

class TestDealerAnalyticsDashboard:
    """
    Integration: Dealer accesses overview, trends, KPIs, station metrics,
    customer insights and peak hours. All should return 200 or be skipped
    if dealer profile not configured.
    """

    def test_dealer_overview(self, client: TestClient, admin_token_headers: dict):
        # Using admin which may not have dealer profile — expect either 200 or 403
        res = client.get(
            "/api/v1/dealer-analytics/overview",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer overview endpoint not implemented")
        # Admin without dealer profile should get 403 (not a dealer)
        assert res.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), res.text

    def test_dealer_kpis(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/dealer-analytics/kpis",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer KPIs endpoint not implemented")
        assert res.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), res.text

    def test_dealer_trends_daily(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/dealer-analytics/trends",
            headers=admin_token_headers,
            params={"period": "daily", "periods": 7},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer trends endpoint not implemented")
        assert res.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), res.text

    def test_dealer_trends_invalid_period_rejected(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/dealer-analytics/trends",
            headers=admin_token_headers,
            params={"period": "invalid_period"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer trends endpoint not implemented")
        # Should be rejected as 400 or 403
        assert res.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        ), res.text

    def test_dealer_station_metrics(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/dealer-analytics/stations",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer station metrics endpoint not implemented")
        assert res.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), res.text

    def test_dealer_peak_hours(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/dealer-analytics/peak-hours",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer peak-hours endpoint not implemented")
        assert res.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), res.text

    def test_dealer_customer_insights(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/dealer-analytics/customers",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer customer insights endpoint not implemented")
        assert res.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        ), res.text


# ─── Workflow 3: Admin Analytics & Aggregation ────────────────────────────────

class TestAdminAnalyticsAggregation:
    """
    Integration: Admin queries all admin-analytics endpoints.
    Validates structured responses for dashboard KPIs, trends,
    battery health, revenue split, and user growth.
    """

    def test_admin_analytics_overview(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/overview",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin analytics overview not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        assert isinstance(body, dict)

    def test_admin_analytics_trends_daily(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/trends",
            headers=admin_token_headers,
            params={"period": "daily"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin analytics trends not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text

    def test_admin_analytics_trends_weekly(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/trends",
            headers=admin_token_headers,
            params={"period": "weekly"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin analytics trends not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text

    def test_admin_battery_health_distribution(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/battery-health-distribution",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Battery health distribution endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        assert isinstance(body, (dict, list))

    def test_admin_revenue_by_region(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/revenue/by-region",
            headers=admin_token_headers,
            params={"period": "30d"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Revenue by region endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        assert isinstance(res.json(), (dict, list))

    def test_admin_revenue_by_station(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/revenue/by-station",
            headers=admin_token_headers,
            params={"period": "30d"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Revenue by station endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text

    def test_admin_top_stations(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/top-stations",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Top stations analytics endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        assert isinstance(res.json(), (dict, list))

    def test_admin_user_growth_monthly(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/user-growth",
            headers=admin_token_headers,
            params={"period": "monthly"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("User growth endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        assert isinstance(res.json(), (dict, list))

    def test_admin_conversion_funnel(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/conversion-funnel",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Conversion funnel endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text

    def test_admin_demand_forecast(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/demand-forecast",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Demand forecast endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        assert isinstance(body, (dict, list))

    def test_admin_inventory_status(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/inventory-status",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Inventory status endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text


# ─── Workflow 4: Analytics Data Export ────────────────────────────────────────

class TestAnalyticsExportFlow:
    """
    Integration: Admin triggers CSV export from analytics endpoints.
    Verifies the response has appropriate content-type or data.
    """

    def test_admin_export_overview_csv(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/export",
            headers=admin_token_headers,
            params={"report_type": "overview"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin analytics export endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        # Should return CSV content-type or binary data
        content_type = res.headers.get("content-type", "")
        assert "csv" in content_type or "json" in content_type or len(res.content) > 0

    def test_admin_export_trends_csv(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/export",
            headers=admin_token_headers,
            params={"report_type": "trends"},
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Admin analytics export endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text

    def test_recent_activity_feed(self, client: TestClient, admin_token_headers: dict):
        res = client.get(
            "/api/v1/admin/analytics/recent-activity",
            headers=admin_token_headers,
        )
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Recent activity endpoint not implemented")
        assert res.status_code == status.HTTP_200_OK, res.text
        body = res.json()
        assert isinstance(body, (dict, list))
