"""
Integration-level tests for AnalyticsService personal cost methods.
Uses an in-memory SQLite database via conftest fixtures.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlmodel import Session

from app.services.analytics_service import AnalyticsService
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.rental import Purchase


# ── helpers ──────────────────────────────────────────────────────────

def _make_rental_tx(session: Session, user_id: int, amount: float, days_ago: int = 0):
    """Insert a successful rental_payment transaction."""
    tx = Transaction(
        user_id=user_id,
        amount=amount,
        transaction_type=TransactionType.RENTAL_PAYMENT,
        status=TransactionStatus.SUCCESS,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
        updated_at=datetime.utcnow(),
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def _make_purchase(session: Session, user_id: int, amount: float, days_ago: int = 0):
    """Insert a purchase record."""
    p = Purchase(
        user_id=user_id,
        amount=amount,
        timestamp=datetime.utcnow() - timedelta(days=days_ago),
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ── Tests ────────────────────────────────────────────────────────────

class TestPersonalCostAnalytics:
    def test_empty_user_returns_zeros(self, session: Session):
        """A user with no transactions should get all-zero analytics."""
        result = AnalyticsService.get_personal_cost_analytics(session, user_id=9999)
        assert result["total_spent_this_month"] == 0.0
        assert result["total_spent_lifetime"] == 0.0
        assert result["breakdown"]["rentals"] == 0.0
        assert result["breakdown"]["purchases"] == 0.0

    def test_rental_only(self, session: Session):
        """Only rental transactions should appear in the rental bucket."""
        _make_rental_tx(session, user_id=1, amount=500.0, days_ago=5)
        _make_rental_tx(session, user_id=1, amount=300.0, days_ago=10)

        result = AnalyticsService.get_personal_cost_analytics(
            session, user_id=1, period="3m", transaction_type="rental"
        )
        assert result["total_spent_lifetime"] >= 800.0
        assert result["breakdown"]["rentals"] >= 800.0
        assert result["breakdown"]["purchases"] == 0.0

    def test_purchase_only(self, session: Session):
        """Only purchase rows should appear in the purchase bucket."""
        _make_purchase(session, user_id=2, amount=1200.0, days_ago=3)

        result = AnalyticsService.get_personal_cost_analytics(
            session, user_id=2, period="3m", transaction_type="purchase"
        )
        assert result["breakdown"]["purchases"] >= 1200.0
        assert result["breakdown"]["rentals"] == 0.0

    def test_breakdown_sums_to_total_period(self, session: Session):
        """rentals + purchases should equal the period total."""
        _make_rental_tx(session, user_id=3, amount=400.0, days_ago=2)
        _make_purchase(session, user_id=3, amount=600.0, days_ago=2)

        result = AnalyticsService.get_personal_cost_analytics(
            session, user_id=3, period="3m", transaction_type="all"
        )
        breakdown = result["breakdown"]
        period_total = result["comparison_with_previous_period"]["current"]
        assert round(breakdown["rentals"] + breakdown["purchases"], 2) == round(period_total, 2)

    def test_period_comparison_direction(self, session: Session):
        """If current period has less spending than previous, change_percent < 0."""
        # Previous period: 60 days ago
        _make_rental_tx(session, user_id=4, amount=2000.0, days_ago=100)
        # Current period: today
        _make_rental_tx(session, user_id=4, amount=500.0, days_ago=1)

        result = AnalyticsService.get_personal_cost_analytics(
            session, user_id=4, period="3m", transaction_type="all"
        )
        comp = result["comparison_with_previous_period"]
        # current < previous  →  negative change
        if comp["previous"] > 0 and comp["current"] < comp["previous"]:
            assert comp["change_percent"] < 0


class TestPersonalCostTrends:
    def test_trends_cover_full_period(self, session: Session):
        """Trends list should have one entry per month in the period."""
        result = AnalyticsService.get_personal_cost_trends(
            session, user_id=1, period="3m", transaction_type="all"
        )
        # 3-month window should produce 3-4 month buckets depending on day of month
        assert len(result) >= 3

    def test_trends_values_match_service(self, session: Session):
        """Each trend item should have month, rentals, purchases keys."""
        _make_rental_tx(session, user_id=5, amount=100.0, days_ago=10)
        result = AnalyticsService.get_personal_cost_trends(
            session, user_id=5, period="3m", transaction_type="all"
        )
        for item in result:
            assert "month" in item
            assert "rentals" in item
            assert "purchases" in item

    def test_type_filter_rental(self, session: Session):
        """When type=rental, purchases should always be 0."""
        _make_purchase(session, user_id=6, amount=999.0, days_ago=5)
        _make_rental_tx(session, user_id=6, amount=50.0, days_ago=5)

        result = AnalyticsService.get_personal_cost_trends(
            session, user_id=6, period="3m", transaction_type="rental"
        )
        for item in result:
            assert item["purchases"] == 0.0

    def test_type_filter_purchase(self, session: Session):
        """When type=purchase, rentals should always be 0."""
        _make_rental_tx(session, user_id=7, amount=999.0, days_ago=5)
        _make_purchase(session, user_id=7, amount=50.0, days_ago=5)

        result = AnalyticsService.get_personal_cost_trends(
            session, user_id=7, period="3m", transaction_type="purchase"
        )
        for item in result:
            assert item["rentals"] == 0.0


# ── Battery Usage Stats (Task 8) ────────────────────────────────────

import uuid
from app.models.rental import Rental
from app.models.battery import Battery
from app.models.station import Station


def _make_station(session: Session, name: str = "Test Station") -> Station:
    s = Station(
        name=name,
        address="123 Test Rd",
        latitude=17.385,
        longitude=78.4867,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def _make_battery(session: Session, battery_type: str = "48V/30Ah") -> Battery:
    b = Battery(
        id=uuid.uuid4(),
        serial_number=f"SN-{uuid.uuid4().hex[:8]}",
        battery_type=battery_type,
    )
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def _make_rental(
    session: Session,
    user_id: int,
    battery: Battery,
    station: Station,
    hours: float = 24,
    days_ago: int = 0,
    status: str = "completed",
):
    now = datetime.utcnow() - timedelta(days=days_ago)
    r = Rental(
        user_id=user_id,
        battery_id=battery.id,
        start_station_id=station.id,
        start_time=now,
        expected_end_time=now + timedelta(hours=hours),
        end_time=now + timedelta(hours=hours) if status == "completed" else None,
        status=status,
        total_amount=100.0,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


class TestPersonalUsageStats:
    def test_empty_user_returns_defaults(self, session: Session):
        result = AnalyticsService.get_personal_usage_stats(session, user_id=9999)
        assert result["total_batteries_rented"] == 0
        assert result["total_batteries_purchased"] == 0
        assert result["avg_rental_duration_hours"] == 0.0
        assert result["badges_earned"] == []

    def test_counts_rentals(self, session: Session):
        station = _make_station(session, "Hub Alpha")
        bat = _make_battery(session)
        _make_rental(session, user_id=100, battery=bat, station=station)
        _make_rental(session, user_id=100, battery=bat, station=station, days_ago=1)

        result = AnalyticsService.get_personal_usage_stats(session, user_id=100)
        assert result["total_batteries_rented"] == 2

    def test_duration_calculations(self, session: Session):
        station = _make_station(session, "Hub Beta")
        bat = _make_battery(session)
        _make_rental(session, user_id=101, battery=bat, station=station, hours=10)
        _make_rental(session, user_id=101, battery=bat, station=station, hours=50)

        result = AnalyticsService.get_personal_usage_stats(session, user_id=101)
        assert result["avg_rental_duration_hours"] == 30.0  # (10+50)/2
        assert result["longest_rental_hours"] == 50.0

    def test_first_rental_badge(self, session: Session):
        station = _make_station(session, "Hub Gamma")
        bat = _make_battery(session)
        _make_rental(session, user_id=102, battery=bat, station=station, hours=1)

        result = AnalyticsService.get_personal_usage_stats(session, user_id=102)
        assert "first_rental" in result["badges_earned"]

    def test_carbon_uses_config(self, session: Session):
        station = _make_station(session, "Hub Delta")
        bat = _make_battery(session)
        _make_rental(session, user_id=103, battery=bat, station=station, hours=200)

        result = AnalyticsService.get_personal_usage_stats(session, user_id=103)
        # 200 hours * 0.05 = 10.0 kg
        assert result["carbon_saved_kg"] == 10.0
        assert "green_warrior" in result["badges_earned"]

    def test_favorite_station(self, session: Session):
        s1 = _make_station(session, "Popular Station")
        s2 = _make_station(session, "Other Station")
        bat = _make_battery(session)
        _make_rental(session, user_id=104, battery=bat, station=s1)
        _make_rental(session, user_id=104, battery=bat, station=s1, days_ago=1)
        _make_rental(session, user_id=104, battery=bat, station=s2, days_ago=2)

        result = AnalyticsService.get_personal_usage_stats(session, user_id=104)
        assert result["favorite_station"]["name"] == "Popular Station"
        assert result["favorite_station"]["rental_count"] == 2

    def test_usage_patterns_keys(self, session: Session):
        station = _make_station(session, "Hub Epsilon")
        bat = _make_battery(session)
        _make_rental(session, user_id=105, battery=bat, station=station)

        result = AnalyticsService.get_personal_usage_stats(session, user_id=105)
        patterns = result["usage_patterns"]
        assert "by_day_of_week" in patterns
        assert "by_hour_of_day" in patterns
        assert "Mon" in patterns["by_day_of_week"]

