"""
Unit tests for the Personal Cost Analytics API endpoints.
Tests the route layer with mocked service methods.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api import deps
from app.models.user import User


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_user():
    """Return a minimal User object for dependency override."""
    user = MagicMock(spec=User)
    user.id = 1
    user.is_active = True
    user.is_deleted = False
    user.is_superuser = False
    return user


@pytest.fixture
def authed_client(mock_user):
    """TestClient where get_current_user is overridden."""
    app.dependency_overrides[deps.get_current_user] = lambda: mock_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


MOCK_ANALYTICS = {
    "total_spent_this_month": 2450.00,
    "total_spent_this_year": 18300.00,
    "total_spent_lifetime": 42150.00,
    "avg_monthly_spending": 1525.00,
    "breakdown": {"rentals": 15200.00, "purchases": 26950.00},
    "month_over_month_change": -12.5,
    "trends": [
        {"month": "2026-01", "rentals": 1200, "purchases": 3400},
        {"month": "2026-02", "rentals": 1800, "purchases": 0},
        {"month": "2026-03", "rentals": 650, "purchases": 0},
    ],
    "comparison_with_previous_period": {
        "current": 2450.00,
        "previous": 2800.00,
        "change_percent": -12.5,
    },
}

MOCK_TRENDS = [
    {"month": "2026-01", "rentals": 1200, "purchases": 3400},
    {"month": "2026-02", "rentals": 1800, "purchases": 0},
    {"month": "2026-03", "rentals": 650, "purchases": 0},
]

SERVICE_PATH = "app.api.v1.user_analytics.AnalyticsService"


# ── GET /cost-analytics ─────────────────────────────────────────────

class TestCostAnalyticsEndpoint:
    @patch(f"{SERVICE_PATH}.get_personal_cost_analytics", return_value=MOCK_ANALYTICS)
    def test_default_params(self, mock_svc, authed_client):
        resp = authed_client.get("/api/v1/customer/users/me/cost-analytics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total_spent_this_month"] == 2450.00
        assert body["data"]["breakdown"]["rentals"] == 15200.00
        mock_svc.assert_called_once()

    @patch(f"{SERVICE_PATH}.get_personal_cost_analytics", return_value=MOCK_ANALYTICS)
    def test_with_period_and_type(self, mock_svc, authed_client):
        resp = authed_client.get(
            "/api/v1/customer/users/me/cost-analytics?period=6m&type=rental"
        )
        assert resp.status_code == 200
        # Verify the service was called with the right args
        args = mock_svc.call_args
        assert args[0][2] == "6m"  # period
        assert args[0][3] == "rental"  # type

    def test_invalid_period(self, authed_client):
        resp = authed_client.get(
            "/api/v1/customer/users/me/cost-analytics?period=99y"
        )
        assert resp.status_code == 422  # validation error

    def test_unauthenticated(self):
        """Without auth override, the endpoint should reject."""
        client = TestClient(app)
        resp = client.get("/api/v1/customer/users/me/cost-analytics")
        assert resp.status_code in (401, 403)


# ── GET /cost-analytics/trends ──────────────────────────────────────

class TestCostTrendsEndpoint:
    @patch(f"{SERVICE_PATH}.get_personal_cost_trends", return_value=MOCK_TRENDS)
    def test_default_params(self, mock_svc, authed_client):
        resp = authed_client.get("/api/v1/customer/users/me/cost-analytics/trends")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]["trends"]) == 3
        assert body["data"]["trends"][0]["month"] == "2026-01"

    @patch(f"{SERVICE_PATH}.get_personal_cost_trends", return_value=MOCK_TRENDS)
    def test_filter_by_purchase(self, mock_svc, authed_client):
        resp = authed_client.get(
            "/api/v1/customer/users/me/cost-analytics/trends?type=purchase&period=1y"
        )
        assert resp.status_code == 200
        args = mock_svc.call_args
        assert args[0][2] == "1y"
        assert args[0][3] == "purchase"

    def test_invalid_type(self, authed_client):
        resp = authed_client.get(
            "/api/v1/customer/users/me/cost-analytics/trends?type=invalid"
        )
        assert resp.status_code == 422


# ── GET /usage-stats (Task 8) ───────────────────────────────────────

MOCK_USAGE_STATS = {
    "total_batteries_rented": 23,
    "total_batteries_purchased": 4,
    "avg_rental_duration_hours": 72.5,
    "longest_rental_hours": 168,
    "most_rented_battery_type": "48V/30Ah",
    "usage_patterns": {
        "by_day_of_week": {"Mon": 5, "Tue": 3, "Wed": 2, "Thu": 4, "Fri": 6, "Sat": 2, "Sun": 1},
        "by_hour_of_day": {"9": 4, "10": 6, "14": 8, "17": 3},
        "peak_usage_day": "Friday",
        "peak_usage_hour": "14:00",
    },
    "carbon_saved_kg": 12.4,
    "favorite_station": {"id": 1, "name": "WEZU Hub - Banjara Hills", "rental_count": 8},
    "current_streak_days": 0,
    "badges_earned": ["first_rental", "green_warrior", "regular_user"],
}


class TestUsageStatsEndpoint:
    @patch(f"{SERVICE_PATH}.get_personal_usage_stats", return_value=MOCK_USAGE_STATS)
    def test_default_response(self, mock_svc, authed_client):
        resp = authed_client.get("/api/v1/customer/users/me/usage-stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total_batteries_rented"] == 23
        assert body["data"]["carbon_saved_kg"] == 12.4
        assert "first_rental" in body["data"]["badges_earned"]
        mock_svc.assert_called_once()

    @patch(f"{SERVICE_PATH}.get_personal_usage_stats", return_value=MOCK_USAGE_STATS)
    def test_response_has_usage_patterns(self, mock_svc, authed_client):
        resp = authed_client.get("/api/v1/customer/users/me/usage-stats")
        body = resp.json()
        patterns = body["data"]["usage_patterns"]
        assert "by_day_of_week" in patterns
        assert "by_hour_of_day" in patterns
        assert patterns["peak_usage_day"] == "Friday"

    @patch(f"{SERVICE_PATH}.get_personal_usage_stats", return_value=MOCK_USAGE_STATS)
    def test_response_has_favorite_station(self, mock_svc, authed_client):
        resp = authed_client.get("/api/v1/customer/users/me/usage-stats")
        body = resp.json()
        fav = body["data"]["favorite_station"]
        assert fav["name"] == "WEZU Hub - Banjara Hills"
        assert fav["rental_count"] == 8

    def test_unauthenticated(self):
        client = TestClient(app)
        resp = client.get("/api/v1/customer/users/me/usage-stats")
        assert resp.status_code in (401, 403)

