from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import select

from app.core.security import create_access_token, create_refresh_token
from app.models.driver_profile import DriverProfile
from app.models.logistics import DeliveryOrder, DeliveryStatus, DeliveryType
from app.models.maintenance import MaintenanceRecord, MaintenanceSchedule
from app.models.session import UserSession
from app.models.station import Station
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.driver_service import DriverService
from app.services.maintenance_service import MaintenanceService


def _first_user(session) -> User:
    user = session.exec(select(User)).first()
    assert user is not None
    return user


def test_get_maintenance_history_returns_battery_records_only(session):
    user = _first_user(session)
    now = datetime.now(UTC)

    station = Station(name="Station A", address="Addr", latitude=12.9, longitude=77.6)
    session.add(station)
    session.commit()
    session.refresh(station)

    battery_id = 101
    session.add(
        MaintenanceRecord(
            entity_type="battery",
            entity_id=battery_id,
            technician_id=user.id,
            maintenance_type="preventive",
            description="older",
            performed_at=now - timedelta(days=3),
        )
    )
    session.add(
        MaintenanceRecord(
            entity_type="battery",
            entity_id=battery_id,
            technician_id=user.id,
            maintenance_type="corrective",
            description="latest",
            performed_at=now - timedelta(days=1),
        )
    )
    session.add(
        MaintenanceRecord(
            entity_type="station",
            entity_id=station.id,
            technician_id=user.id,
            maintenance_type="preventive",
            description="station maintenance",
            performed_at=now - timedelta(days=2),
        )
    )
    session.commit()

    history = MaintenanceService.get_maintenance_history(session, battery_id)
    assert len(history) == 2
    assert [item.description for item in history] == ["latest", "older"]
    assert all(item.entity_type == "battery" for item in history)


def test_get_maintenance_schedule_returns_upcoming_overdue_and_history(session):
    user = _first_user(session)
    now = datetime.now(UTC)

    station = Station(name="Station B", address="Addr", latitude=13.0, longitude=77.7)
    session.add(station)
    session.commit()
    session.refresh(station)

    session.add(
        MaintenanceSchedule(
            entity_type="station",
            model_name="standard",
            interval_days=7,
            checklist='["inspect"]',
            next_maintenance_date=now + timedelta(days=2),
        )
    )
    session.add(
        MaintenanceSchedule(
            entity_type="station",
            model_name="standard",
            interval_days=7,
            checklist='["repair"]',
            next_maintenance_date=now - timedelta(days=2),
        )
    )
    session.add(
        MaintenanceRecord(
            entity_type="station",
            entity_id=station.id,
            technician_id=user.id,
            maintenance_type="preventive",
            description="station check",
            performed_at=now - timedelta(hours=6),
        )
    )
    session.commit()

    payload = MaintenanceService.get_maintenance_schedule(session, station.id)
    assert payload["station_id"] == station.id
    assert len(payload["overdue"]) == 1
    assert len(payload["upcoming"]) >= 1
    assert len(payload["history"]) == 1
    assert payload["history"][0].description == "station check"


def test_get_driver_dashboard_stats_aggregates_order_counts(session):
    base_user = _first_user(session)

    driver_user = User(
        phone_number="7777777777",
        email="driver@test.com",
        full_name="Driver User",
        hashed_password=base_user.hashed_password,
    )
    session.add(driver_user)
    session.commit()
    session.refresh(driver_user)

    driver = DriverProfile(
        user_id=driver_user.id,
        license_number="LIC-123",
        vehicle_type="scooter",
        vehicle_plate="KA01AB1234",
        rating=4.8,
        total_deliveries=10,
        on_time_deliveries=8,
        total_delivery_time_seconds=7200,
        satisfaction_sum=42.0,
    )
    session.add(driver)
    session.commit()
    session.refresh(driver)

    session.add(
        DeliveryOrder(
            order_type=DeliveryType.CUSTOMER_DELIVERY,
            origin_address="A",
            destination_address="B",
            assigned_driver_id=driver_user.id,
            status=DeliveryStatus.DELIVERED,
        )
    )
    session.add(
        DeliveryOrder(
            order_type=DeliveryType.CUSTOMER_DELIVERY,
            origin_address="C",
            destination_address="D",
            assigned_driver_id=driver_user.id,
            status=DeliveryStatus.IN_TRANSIT,
        )
    )
    session.add(
        DeliveryOrder(
            order_type=DeliveryType.CUSTOMER_DELIVERY,
            origin_address="E",
            destination_address="F",
            assigned_driver_id=driver_user.id,
            status=DeliveryStatus.ASSIGNED,
        )
    )
    session.commit()

    stats = DriverService.get_driver_dashboard_stats(session, driver.id)
    assert stats["driver_id"] == driver.id
    assert stats["total_jobs"] == 3
    assert stats["completed_jobs"] == 1
    assert stats["active_jobs"] == 2
    assert stats["rating"] == 4.8
    assert stats["on_time_rate"] == 80.0


def test_create_session_persists_user_session_for_passkey_contract(session):
    user = _first_user(session)
    sid = str(uuid4())
    access_token = create_access_token(subject=user.id, extra_claims={"sid": sid})
    refresh_token = create_refresh_token(subject=user.id, jti=sid)

    created = AuthService.create_session(
        session,
        user.id,
        access_token,
        refresh_token,
        device_info="Passkey",
        ip_address="203.0.113.10",
    )

    assert created is not None
    assert created.user_id == user.id
    assert created.token_id == sid
    assert created.device_name == "Passkey"
    assert created.ip_address == "203.0.113.10"
    assert created.refresh_token_hash
    assert created.refresh_token_hash != refresh_token

    persisted = session.exec(
        select(UserSession).where(UserSession.user_id == user.id).where(UserSession.token_id == sid)
    ).first()
    assert persisted is not None
