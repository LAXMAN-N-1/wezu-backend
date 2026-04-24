from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.models.battery import Battery
from app.models.battery_health import BatteryHealthSnapshot
from app.models.financial import Transaction, TransactionStatus, TransactionType
from app.models.rental import Rental, RentalStatus
from app.models.station import Station
from app.models.support import SupportTicket, TicketPriority, TicketStatus
from app.models.user import User, UserStatus, UserType
from app.services.analytics_service import AnalyticsService
from app.utils.runtime_cache import invalidate_cache


def _admin_user(session: Session) -> User:
    user = session.exec(select(User).where(User.email == "admin@test.com")).first()
    assert user is not None
    return user


def _override_admin(client: TestClient, user: User) -> None:
    client.app.dependency_overrides[deps.get_current_active_admin] = lambda: user


def _dashboard_payload() -> dict:
    return {
        "period": "30d",
        "generated_at": datetime.now(UTC),
        "overview": {"total_revenue": {"label": "Total Revenue", "value": 1250}},
        "trends": {"period": "30d", "data": []},
        "conversion_funnel": {"stages": []},
        "battery_health_distribution": {"distribution": [], "total": 0},
        "inventory_status": {"inventory": [], "total_batteries": 0},
        "demand_forecast": {"forecast": []},
        "revenue_by_station": {"stations": [], "total_revenue": 0},
        "recent_activity": {"activities": []},
        "top_stations": {"stations": []},
    }


def test_admin_dashboard_bootstrap_endpoint(client: TestClient, session: Session):
    user = _admin_user(session)
    _override_admin(client, user)
    invalidate_cache("admin-analytics")

    with patch.object(
        AnalyticsService,
        "get_admin_dashboard_bootstrap",
        return_value=_dashboard_payload(),
    ) as mocked:
        response = client.get(f"{settings.API_V1_STR}/admin/analytics/dashboard?period=30d")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "30d"
    assert body["overview"]["total_revenue"]["value"] == 1250
    assert "generated_at" in body
    mocked.assert_called_once()


def test_admin_dashboard_bootstrap_uses_shared_cache(client: TestClient, session: Session):
    user = _admin_user(session)
    _override_admin(client, user)
    invalidate_cache("admin-analytics")

    payload = _dashboard_payload()
    with patch.object(
        AnalyticsService,
        "get_admin_dashboard_bootstrap",
        side_effect=[payload, payload],
    ) as mocked:
        first = client.get(f"{settings.API_V1_STR}/admin/analytics/dashboard?period=30d")
        second = client.get(f"{settings.API_V1_STR}/admin/analytics/dashboard?period=30d")

    assert first.status_code == 200
    assert second.status_code == 200
    assert mocked.call_count == 1


def test_admin_overview_endpoint_stays_available(client: TestClient, session: Session):
    user = _admin_user(session)
    _override_admin(client, user)
    invalidate_cache("admin-analytics")

    sample_overview = {
        "total_revenue": {"label": "Total Revenue", "value": 999},
        "active_rentals": {"label": "Active Rentals", "value": 3},
    }
    with patch.object(
        AnalyticsService,
        "get_platform_overview",
        return_value=sample_overview,
    ):
        response = client.get(f"{settings.API_V1_STR}/admin/analytics/overview?period=30d")

    assert response.status_code == 200
    assert response.json()["total_revenue"]["value"] == 999


def test_recent_activity_merges_and_sorts_sources(session: Session):
    now = datetime.now(UTC)
    user = User(
        email="analytics-customer@test.com",
        phone_number="7000000001",
        user_type=UserType.CUSTOMER,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    station = Station(
        name="Analytics Station",
        address="Road 1",
        latitude=17.0,
        longitude=78.0,
    )
    session.add(station)
    session.commit()
    session.refresh(station)

    battery = Battery(
        serial_number="BAT-AN-001",
        qr_code_data="BAT-AN-001",
        station_id=station.id,
        health_percentage=92.0,
    )
    session.add(battery)
    session.commit()
    session.refresh(battery)

    rental = Rental(
        user_id=user.id,
        battery_id=battery.id,
        start_station_id=station.id,
        expected_end_time=now + timedelta(hours=2),
        total_amount=150.0,
        created_at=now - timedelta(minutes=20),
    )
    payment = Transaction(
        user_id=user.id,
        rental_id=None,
        amount=240.0,
        transaction_type=TransactionType.RENTAL_PAYMENT,
        status=TransactionStatus.SUCCESS,
        payment_method="upi",
        created_at=now - timedelta(minutes=5),
    )
    ticket = SupportTicket(
        user_id=user.id,
        subject="Battery issue",
        description="Needs inspection",
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        created_at=now - timedelta(minutes=10),
    )
    session.add(rental)
    session.add(payment)
    session.add(ticket)
    session.commit()

    result = AnalyticsService.get_recent_activity(session, limit=3)

    assert [item["type"] for item in result["activities"]] == [
        "payment",
        "alert",
        "rental",
    ]


def test_battery_health_distribution_uses_bucketed_counts(session: Session):
    now = datetime.now(UTC)
    battery_specs = [
        ("BAT-HEALTH-1", "BAT-HEALTH-1", 95.0),
        ("BAT-HEALTH-2", "BAT-HEALTH-2", 84.0),
        ("BAT-HEALTH-3", "BAT-HEALTH-3", 72.0),
        ("BAT-HEALTH-4", "BAT-HEALTH-4", 61.0),
    ]
    battery_ids = []
    for serial, qr_code, health in battery_specs:
        battery = Battery(
            serial_number=serial,
            qr_code_data=qr_code,
            health_percentage=health,
        )
        session.add(battery)
        session.commit()
        session.refresh(battery)
        battery_ids.append(battery.id)

    snapshots = [
        BatteryHealthSnapshot(
            battery_id=battery_ids[0],
            health_percentage=91.0,
            recorded_at=now - timedelta(days=45),
        ),
        BatteryHealthSnapshot(
            battery_id=battery_ids[1],
            health_percentage=81.0,
            recorded_at=now - timedelta(days=45),
        ),
        BatteryHealthSnapshot(
            battery_id=battery_ids[2],
            health_percentage=68.0,
            recorded_at=now - timedelta(days=45),
        ),
    ]
    session.add_all(snapshots)
    session.commit()

    result = AnalyticsService.get_battery_health_distribution(session)

    counts = {item["category"]: item["count"] for item in result["distribution"]}
    assert counts["Excellent (90-100%)"] == 1
    assert counts["Good (80-89%)"] == 1
    assert counts["Fair (70-79%)"] == 1
    assert counts["Critical (<70%)"] == 1
    previous_counts = {
        item["category"]: item["count"] for item in result["previous_distribution"]
    }
    assert previous_counts["Excellent (90-100%)"] == 1
    assert previous_counts["Good (80-89%)"] == 1
    assert previous_counts["Critical (<70%)"] == 1
