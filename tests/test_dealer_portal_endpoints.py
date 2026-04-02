"""
Tests for the 5 new Dealer Portal endpoints:
  1. GET  /api/v1/dealer/analytics/revenue-chart
  2. GET  /api/v1/dealer/analytics/commission-summary
  3. GET  /api/v1/dealer/portal/payouts
  4. GET  /api/v1/dealer/portal/transactions/{id}
  5. POST /api/v1/dealer/portal/transactions/{id}/dispute

Covers unit tests for service methods AND integration tests hitting
the real endpoints via TestClient.
"""

import pytest
from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select

from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile
from app.models.station import Station
from app.models.battery import Battery
from app.models.swap import SwapSession
from app.models.rental import Rental, RentalStatus
from app.models.rental_event import RentalEvent
from app.models.settlement import Settlement
from app.models.settlement_dispute import SettlementDispute
from app.models.commission import CommissionLog, CommissionConfig
from app.models.rbac import Role
from app.core.security import get_password_hash


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def dealer_role(session: Session):
    role = session.exec(select(Role).where(Role.name == "dealer")).first()
    if not role:
        role = Role(name="dealer", slug="dealer", description="Dealer role", is_system_role=True)
        session.add(role)
        session.commit()
        session.refresh(role)
    return role


@pytest.fixture
def dealer_user(session: Session, dealer_role: Role):
    user = User(
        phone_number="8888888888",
        email="dealer@test.com",
        full_name="Test Dealer",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=False,
        status=UserStatus.ACTIVE,
        user_type=UserType.DEALER,
        role_id=dealer_role.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def dealer_profile(session: Session, dealer_user: User):
    profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Test Dealer Business",
        contact_person="Test Dealer",
        contact_email="dealer@test.com",
        contact_phone="8888888888",
        address_line1="123 Main Street",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        payout_interval="Weekly",
        min_payout_amount=100.0,
        is_active=True,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@pytest.fixture
def station(session: Session, dealer_profile: DealerProfile):
    stn = Station(
        name="Test Station Alpha",
        address="456 Station Road",
        latitude=19.076,
        longitude=72.8777,
        dealer_id=dealer_profile.id,
        total_slots=10,
        status="active",
    )
    session.add(stn)
    session.commit()
    session.refresh(stn)
    return stn


@pytest.fixture
def customer_user(session: Session):
    user = User(
        phone_number="7777777777",
        email="customer@test.com",
        full_name="Test Customer",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=False,
        status=UserStatus.ACTIVE,
        user_type=UserType.CUSTOMER,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def battery(session: Session, station: Station):
    bat = Battery(
        serial_number="BAT-TEST-001",
        battery_type="lithium",
        capacity_kwh=2.5,
        soc=95.0,
        health_percentage=98.0,
        station_id=station.id,
        status="available",
        purchase_cost=15000.0,
    )
    session.add(bat)
    session.commit()
    session.refresh(bat)
    return bat


@pytest.fixture
def rental(session: Session, customer_user: User, battery: Battery, station: Station):
    now = datetime.now(UTC)
    r = Rental(
        user_id=customer_user.id,
        battery_id=battery.id,
        start_station_id=station.id,
        start_time=now - timedelta(hours=2),
        expected_end_time=now + timedelta(hours=4),
        total_amount=250.0,
        security_deposit=100.0,
        status=RentalStatus.ACTIVE,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@pytest.fixture
def rental_events(session: Session, rental: Rental, station: Station, battery: Battery):
    events = [
        RentalEvent(
            rental_id=rental.id,
            event_type="start",
            description="Rental started",
            station_id=station.id,
            battery_id=battery.id,
        ),
    ]
    for e in events:
        session.add(e)
    session.commit()
    return events


@pytest.fixture
def swap_session(session: Session, rental: Rental, customer_user: User, station: Station, battery: Battery):
    now = datetime.now(UTC)
    swap = SwapSession(
        rental_id=rental.id,
        user_id=customer_user.id,
        station_id=station.id,
        old_battery_id=battery.id,
        new_battery_id=battery.id,
        swap_amount=50.0,
        status="completed",
        payment_status="paid",
        completed_at=now,
    )
    session.add(swap)
    session.commit()
    session.refresh(swap)
    return swap


@pytest.fixture
def settlement(session: Session, dealer_user: User):
    now = datetime.now(UTC)
    month_str = now.strftime("%Y-%m")
    s = Settlement(
        dealer_id=dealer_user.id,
        settlement_month=month_str,
        start_date=now.replace(day=1),
        end_date=now,
        due_date=now + timedelta(days=10),
        total_revenue=5000.0,
        total_commission=500.0,
        chargeback_amount=50.0,
        platform_fee=100.0,
        net_payable=350.0,
        status="generated",
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@pytest.fixture
def dealer_token(client, dealer_user: User):
    """Get auth token for dealer user."""
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": dealer_user.email, "password": "password"},
    )
    if resp.status_code == 200:
        return resp.json().get("access_token")
    # Fallback: generate token directly
    from app.core.security import create_access_token
    return create_access_token(subject=str(dealer_user.id))


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════
# UNIT TESTS — Service Layer
# ═══════════════════════════════════════════════════════════════


class TestDealerAnalyticsServiceUnit:

    def test_get_revenue_chart_data_returns_correct_structure(
        self, session, dealer_profile, station, swap_session
    ):
        from app.services.dealer_analytics_service import DealerAnalyticsService

        result = DealerAnalyticsService.get_revenue_chart_data(
            session, dealer_profile.id, granularity="daily", periods=3
        )

        assert "granularity" in result
        assert result["granularity"] == "daily"
        assert "current" in result
        assert len(result["current"]) == 3
        assert "previous" not in result  # compare=False by default

        # Each data point should have label, revenue, swap_count
        for point in result["current"]:
            assert "label" in point
            assert "revenue" in point
            assert "swap_count" in point

    def test_get_revenue_chart_data_with_comparison(
        self, session, dealer_profile, station
    ):
        from app.services.dealer_analytics_service import DealerAnalyticsService

        result = DealerAnalyticsService.get_revenue_chart_data(
            session, dealer_profile.id, granularity="daily", periods=3, compare=True
        )

        assert "current" in result
        assert "previous" in result
        assert len(result["previous"]) == 3

    def test_get_revenue_chart_hourly_granularity(
        self, session, dealer_profile, station
    ):
        from app.services.dealer_analytics_service import DealerAnalyticsService

        result = DealerAnalyticsService.get_revenue_chart_data(
            session, dealer_profile.id, granularity="hourly", periods=6
        )

        assert result["granularity"] == "hourly"
        assert len(result["current"]) == 6
        # Labels should be like "HH:MM"
        for point in result["current"]:
            assert ":" in point["label"]

    def test_get_revenue_chart_weekly_granularity(
        self, session, dealer_profile, station
    ):
        from app.services.dealer_analytics_service import DealerAnalyticsService

        result = DealerAnalyticsService.get_revenue_chart_data(
            session, dealer_profile.id, granularity="weekly", periods=4
        )

        assert result["granularity"] == "weekly"
        assert len(result["current"]) == 4

    def test_get_commission_summary_returns_correct_structure(
        self, session, dealer_profile, station, swap_session, settlement
    ):
        from app.services.dealer_analytics_service import DealerAnalyticsService

        result = DealerAnalyticsService.get_commission_summary(
            session, dealer_profile.id
        )

        assert "period" in result
        assert "start" in result["period"]
        assert "end" in result["period"]
        assert "gross_revenue" in result
        assert "platform_fees" in result
        assert "commission_earned" in result
        assert "net_payout" in result

    def test_get_commission_summary_with_custom_dates(
        self, session, dealer_profile, station
    ):
        from app.services.dealer_analytics_service import DealerAnalyticsService

        now = datetime.now(UTC)
        start = now - timedelta(days=30)

        result = DealerAnalyticsService.get_commission_summary(
            session, dealer_profile.id, start_date=start, end_date=now
        )

        assert result["gross_revenue"] >= 0
        assert result["platform_fees"] >= 0

    def test_get_commission_summary_no_stations_returns_zeros(self, session, dealer_profile):
        """Dealer with no stations should get zero values."""
        from app.services.dealer_analytics_service import DealerAnalyticsService

        # Delete any existing stations for this dealer
        stations = session.exec(
            select(Station).where(Station.dealer_id == dealer_profile.id)
        ).all()
        for s in stations:
            session.delete(s)
        session.commit()

        result = DealerAnalyticsService.get_commission_summary(
            session, dealer_profile.id
        )

        assert result["gross_revenue"] == 0.0


class TestSettlementServiceUnit:

    def test_get_dealer_payouts_structure(
        self, session, dealer_user, dealer_profile, settlement
    ):
        from app.services.settlement_service import SettlementService

        result = SettlementService.get_dealer_payouts(session, dealer_user.id)

        assert "payout_interval" in result
        assert result["payout_interval"] == "Weekly"
        assert "min_payout_amount" in result
        assert "next_payout" in result
        assert "date" in result["next_payout"]
        assert "countdown" in result["next_payout"]
        assert "days" in result["next_payout"]["countdown"]
        assert "hours" in result["next_payout"]["countdown"]
        assert "payouts" in result
        assert "total" in result

    def test_get_dealer_payouts_includes_settlements(
        self, session, dealer_user, dealer_profile, settlement
    ):
        from app.services.settlement_service import SettlementService

        result = SettlementService.get_dealer_payouts(session, dealer_user.id)

        assert result["total"] >= 1
        assert any(p["id"] == settlement.id for p in result["payouts"])

    def test_get_dealer_payouts_countdown_is_positive(
        self, session, dealer_user, dealer_profile
    ):
        from app.services.settlement_service import SettlementService

        result = SettlementService.get_dealer_payouts(session, dealer_user.id)

        assert result["next_payout"]["countdown"]["total_seconds"] >= 0

    def test_get_dealer_payouts_status_summary(
        self, session, dealer_user, dealer_profile, settlement
    ):
        from app.services.settlement_service import SettlementService

        result = SettlementService.get_dealer_payouts(session, dealer_user.id)

        assert "status_summary" in result
        assert "generated" in result["status_summary"]
        assert result["status_summary"]["generated"] >= 1


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS — API Endpoints via TestClient
# ═══════════════════════════════════════════════════════════════


class TestRevenueChartEndpoint:

    def test_revenue_chart_default(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/revenue-chart",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "daily"
        assert len(data["current"]) == 7

    def test_revenue_chart_hourly(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/revenue-chart?granularity=hourly&periods=12",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "hourly"
        assert len(data["current"]) == 12

    def test_revenue_chart_with_comparison(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/revenue-chart?compare=true&periods=5",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "previous" in data
        assert len(data["previous"]) == 5

    def test_revenue_chart_invalid_granularity(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/revenue-chart?granularity=yearly",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 400

    def test_revenue_chart_unauthenticated(self, client):
        resp = client.get("/api/v1/dealer/analytics/revenue-chart")
        assert resp.status_code == 401


class TestCommissionSummaryEndpoint:

    def test_commission_summary_default(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/commission-summary",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "gross_revenue" in data
        assert "platform_fees" in data
        assert "commission_earned" in data
        assert "net_payout" in data
        assert "period" in data

    def test_commission_summary_with_dates(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/commission-summary?start_date=2026-01-01&end_date=2026-12-31",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200

    def test_commission_summary_invalid_date(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/analytics/commission-summary?start_date=not-a-date",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 400

    def test_commission_summary_unauthenticated(self, client):
        resp = client.get("/api/v1/dealer/analytics/commission-summary")
        assert resp.status_code == 401


class TestPayoutsEndpoint:

    def test_payouts_default(self, client, dealer_token, dealer_profile, settlement):
        resp = client.get(
            "/api/v1/dealer/portal/payouts",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "payout_interval" in data
        assert "next_payout" in data
        assert "payouts" in data

    def test_payouts_contains_countdown(self, client, dealer_token, dealer_profile):
        resp = client.get(
            "/api/v1/dealer/portal/payouts",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        countdown = data["next_payout"]["countdown"]
        assert "days" in countdown
        assert "hours" in countdown
        assert countdown["total_seconds"] >= 0

    def test_payouts_unauthenticated(self, client):
        resp = client.get("/api/v1/dealer/portal/payouts")
        assert resp.status_code == 401


class TestTransactionDetailEndpoint:

    def test_transaction_detail_success(
        self, client, dealer_token, dealer_profile, station, rental, rental_events
    ):
        resp = client.get(
            f"/api/v1/dealer/portal/transactions/{rental.id}",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rental.id
        assert "customer" in data
        assert "timeline" in data
        assert len(data["timeline"]) >= 1
        assert "start_station" in data
        assert "linked_swaps" in data

    def test_transaction_detail_not_found(self, client, dealer_token, dealer_profile, station):
        resp = client.get(
            "/api/v1/dealer/portal/transactions/99999",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 404

    def test_transaction_detail_synthesized_timeline(
        self, client, dealer_token, dealer_profile, station, rental
    ):
        """When no RentalEvents exist, timeline should be synthesized from rental data."""
        resp = client.get(
            f"/api/v1/dealer/portal/transactions/{rental.id}",
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["timeline"]) >= 1
        assert data["timeline"][0]["event_type"] == "start"

    def test_transaction_detail_unauthenticated(self, client, rental):
        resp = client.get(f"/api/v1/dealer/portal/transactions/{rental.id}")
        assert resp.status_code == 401


class TestTransactionDisputeEndpoint:

    def test_dispute_success(
        self, client, dealer_token, dealer_profile, station, rental, settlement, session, dealer_user
    ):
        # Create a commission log linking the transaction to the settlement
        from app.models.financial import Transaction
        # We need a transaction record; link the commission log via rental.id
        clog = CommissionLog(
            transaction_id=rental.id,  # Using rental id as transaction reference
            dealer_id=dealer_user.id,
            amount=25.0,
            settlement_id=settlement.id,
        )
        session.add(clog)
        session.commit()

        resp = client.post(
            f"/api/v1/dealer/portal/transactions/{rental.id}/dispute",
            json={"reason": "Incorrect commission calculation"},
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "open"
        assert "transaction_id" in data
        assert data["transaction_id"] == rental.id

    def test_dispute_transaction_not_found(self, client, dealer_token, dealer_profile, station):
        resp = client.post(
            "/api/v1/dealer/portal/transactions/99999/dispute",
            json={"reason": "Test dispute"},
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 404

    def test_dispute_unauthenticated(self, client, rental):
        resp = client.post(
            f"/api/v1/dealer/portal/transactions/{rental.id}/dispute",
            json={"reason": "Test"},
        )
        assert resp.status_code == 401

    def test_dispute_missing_reason(self, client, dealer_token, dealer_profile, station, rental):
        resp = client.post(
            f"/api/v1/dealer/portal/transactions/{rental.id}/dispute",
            json={},
            headers=auth_headers(dealer_token),
        )
        assert resp.status_code == 422  # Pydantic validation error
