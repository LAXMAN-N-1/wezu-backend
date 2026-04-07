from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api import deps
from app.models.battery import Battery
from app.models.battery_reservation import BatteryReservation
from app.models.dealer import DealerProfile
from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.financial import Transaction, TransactionStatus, TransactionType, Wallet
from app.models.rental import Rental
from app.models.station import Station
from app.models.user import User


def _seed_admin(session: Session) -> User:
    admin = session.exec(select(User).where(User.email == "admin@test.com")).first()
    assert admin is not None
    return admin


def _override_admin_auth(client: TestClient, admin_user: User) -> None:
    app = client.app
    app.dependency_overrides[deps.get_current_active_admin] = lambda: admin_user
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin_user


def _create_station(session: Session, *, name: str) -> Station:
    station = Station(
        name=name,
        address=f"{name} Address",
        latitude=12.0,
        longitude=77.0,
        status="active",
    )
    session.add(station)
    session.commit()
    session.refresh(station)
    return station


def _create_battery(session: Session, station_id: int, *, health: float = 90.0, charge: float = 90.0) -> Battery:
    battery = Battery(
        serial_number=f"BAT-{uuid.uuid4().hex[:8]}",
        station_id=station_id,
        status="available",
        current_charge=charge,
        health_percentage=health,
    )
    session.add(battery)
    session.commit()
    session.refresh(battery)
    return battery


def _create_customer(session: Session) -> User:
    user = User(
        phone_number=f"9{uuid.uuid4().int % 10_000_000_000:010d}",
        email=f"cust-{uuid.uuid4().hex[:8]}@example.com",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_dealer_profile(session: Session, user: User) -> DealerProfile:
    dealer = DealerProfile(
        user_id=user.id,
        business_name="Dealer Ops Pvt Ltd",
        contact_person="Dealer Owner",
        contact_email=user.email,
        contact_phone=user.phone_number or "9000000000",
        address_line1="Dealer Street 1",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        is_active=True,
    )
    session.add(dealer)
    session.commit()
    session.refresh(dealer)
    return dealer


def test_dashboard_trend_and_top_stations_are_data_driven(client: TestClient, session: Session):
    admin_user = _seed_admin(session)
    _override_admin_auth(client, admin_user)

    customer = _create_customer(session)

    station_a = _create_station(session, name="Alpha Hub")
    station_b = _create_station(session, name="Beta Hub")

    battery_a = _create_battery(session, station_a.id, health=95.0, charge=85.0)
    battery_b = _create_battery(session, station_b.id, health=82.0, charge=88.0)

    now = datetime.now(UTC)
    rental_a = Rental(
        user_id=customer.id,
        battery_id=battery_a.id,
        start_station_id=station_a.id,
        expected_end_time=now + timedelta(hours=2),
        start_time=now - timedelta(days=1),
        end_time=now - timedelta(days=1) + timedelta(hours=1),
        total_amount=220.0,
        status="completed",
    )
    rental_b = Rental(
        user_id=customer.id,
        battery_id=battery_b.id,
        start_station_id=station_b.id,
        expected_end_time=now + timedelta(hours=3),
        start_time=now - timedelta(days=2),
        end_time=now - timedelta(days=2) + timedelta(hours=1, minutes=30),
        total_amount=80.0,
        status="completed",
    )
    session.add(rental_a)
    session.add(rental_b)
    session.commit()

    from_date = (now - timedelta(days=3)).date().isoformat()
    to_date = now.date().isoformat()

    trend_resp = client.get(
        f"/api/v1/dashboard/trend?from_date={from_date}&to_date={to_date}&granularity=day&metrics=revenue,rentals"
    )
    assert trend_resp.status_code == 200
    points = trend_resp.json()["points"]
    assert sum(float(p.get("revenue", 0.0)) for p in points) == pytest.approx(300.0)
    assert sum(int(p.get("rentals", 0)) for p in points) == 2

    top_resp = client.get("/api/v1/dashboard/top-stations?limit=2")
    assert top_resp.status_code == 200
    stations = top_resp.json()["stations"]
    assert len(stations) == 2
    assert stations[0]["name"] == "Alpha Hub"
    assert stations[0]["revenue"] == pytest.approx(220.0)
    assert stations[1]["name"] == "Beta Hub"
    assert stations[1]["revenue"] == pytest.approx(80.0)


def test_booking_payment_activates_reservation_and_records_transaction(
    client: TestClient,
    session: Session,
    normal_user: User,
):
    client.app.dependency_overrides[deps.get_current_user] = lambda: normal_user

    station = _create_station(session, name="Booking Station")
    battery = _create_battery(session, station.id, health=92.0, charge=91.0)

    wallet = Wallet(user_id=normal_user.id, balance=120.0, currency="INR")
    session.add(wallet)
    session.commit()
    session.refresh(wallet)

    now = datetime.now(UTC)
    booking = BatteryReservation(
        user_id=normal_user.id,
        station_id=station.id,
        battery_id=battery.id,
        start_time=now,
        end_time=now + timedelta(minutes=30),
        status="PENDING",
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)

    pay_resp = client.post(
        f"/api/v1/bookings/{booking.id}/pay",
        json={"amount": 40.0, "payment_method": "wallet"},
    )
    assert pay_resp.status_code == 200
    body = pay_resp.json()
    assert body["booking_id"] == booking.id
    assert body["status"] == "ACTIVE"
    assert body["amount_paid"] == pytest.approx(40.0)

    session.refresh(wallet)
    assert float(wallet.balance) == pytest.approx(80.0)

    session.refresh(booking)
    assert booking.status == "ACTIVE"

    txn = session.exec(
        select(Transaction)
        .where(Transaction.user_id == normal_user.id)
        .order_by(Transaction.created_at.desc())
    ).first()
    assert txn is not None
    assert float(txn.amount) == pytest.approx(40.0)
    assert txn.transaction_type == TransactionType.RENTAL_PAYMENT
    assert txn.status == TransactionStatus.SUCCESS


def test_booking_invalid_transition_rejected(client: TestClient, session: Session, normal_user: User):
    client.app.dependency_overrides[deps.get_current_user] = lambda: normal_user

    station = _create_station(session, name="Transition Station")
    battery = _create_battery(session, station.id, health=88.0, charge=90.0)
    now = datetime.now(UTC)
    booking = BatteryReservation(
        user_id=normal_user.id,
        station_id=station.id,
        battery_id=battery.id,
        start_time=now - timedelta(hours=4),
        end_time=now - timedelta(hours=2),
        status="COMPLETED",
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)

    resp = client.put(
        f"/api/v1/bookings/{booking.id}",
        json={"status": "ACTIVE"},
    )
    assert resp.status_code == 400
    payload = resp.json()
    detail = payload.get("detail") or payload.get("message") or str(payload)
    assert "Cannot transition" in detail


def test_analytics_export_json_and_csv_include_rich_summary(
    client: TestClient,
    session: Session,
    normal_user: User,
):
    client.app.dependency_overrides[deps.get_current_user] = lambda: normal_user

    station = _create_station(session, name="Analytics Station")
    battery = _create_battery(session, station.id, health=90.0, charge=93.0)

    now = datetime.now(UTC)
    rental = Rental(
        user_id=normal_user.id,
        battery_id=battery.id,
        start_station_id=station.id,
        expected_end_time=now + timedelta(hours=2),
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=1),
        total_amount=150.0,
        late_fee=5.0,
        distance_traveled_km=12.5,
        status="completed",
    )
    session.add(rental)
    session.commit()
    session.refresh(rental)

    txn = Transaction(
        user_id=normal_user.id,
        amount=150.0,
        currency="INR",
        transaction_type=TransactionType.RENTAL_PAYMENT,
        status=TransactionStatus.SUCCESS,
        payment_method="wallet",
        description="Rental payment",
        rental_id=rental.id,
    )
    session.add(txn)
    session.commit()

    json_resp = client.get("/api/v1/analytics/export?format=json")
    assert json_resp.status_code == 200
    data = json_resp.json()
    assert data["summary"]["rentals"]["total_count"] == 1
    assert data["summary"]["rentals"]["total_amount"] == pytest.approx(150.0)
    assert data["summary"]["transactions"]["total_count"] == 1
    assert "total_amount" in data["rentals"][0]

    csv_resp = client.get("/api/v1/analytics/export?format=csv")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "section,id,status" in csv_resp.text
    assert "summary,totals" in csv_resp.text


def test_payment_methods_lifecycle_is_persistent_across_wallet_and_payments_routes(
    client: TestClient,
    session: Session,
    normal_user: User,
):
    client.app.dependency_overrides[deps.get_current_user] = lambda: normal_user

    first_add = client.post(
        "/api/v1/wallet/payment-methods",
        json={
            "type": "card",
            "provider_token": "tok_card_4111111111111111",
            "details": {"last4": "1111", "brand": "VISA", "exp_month": 12, "exp_year": 2030},
        },
    )
    assert first_add.status_code == 200
    first_body = first_add.json()
    assert first_body["created"] is True
    assert first_body["method"]["is_default"] is True
    first_method_id = int(first_body["method"]["id"])

    second_add = client.post(
        "/api/v1/payments/methods",
        json={
            "type": "upi",
            "provider_token": "mohit@upi",
            "provider": "razorpay",
            "is_default": True,
            "details": {"vpa": "mohit@upi"},
        },
    )
    assert second_add.status_code == 200
    second_body = second_add.json()
    assert second_body["created"] is True
    second_method_id = int(second_body["method_id"])

    duplicate_add = client.post(
        "/api/v1/payments/methods",
        json={
            "type": "upi",
            "provider_token": "mohit@upi",
            "provider": "razorpay",
            "is_default": True,
            "details": {"vpa": "mohit@upi"},
        },
    )
    assert duplicate_add.status_code == 200
    assert duplicate_add.json()["created"] is False

    wallet_list = client.get("/api/v1/wallet/payment-methods")
    assert wallet_list.status_code == 200
    wallet_payload = wallet_list.json()["data"]
    assert len(wallet_payload["methods"]) == 2
    assert int(wallet_payload["default_method_id"]) == second_method_id

    remove_second = client.delete(f"/api/v1/payments/methods/{second_method_id}")
    assert remove_second.status_code == 200

    methods_payload = client.get("/api/v1/payments/payment-methods")
    assert methods_payload.status_code == 200
    payload = methods_payload.json()["data"]

    assert len(payload["saved_methods"]) == 1
    assert int(payload["saved_methods"][0]["id"]) == first_method_id
    assert payload["saved_methods"][0]["is_default"] is True
    assert payload["default_method_id"] == str(first_method_id)
    assert {row["type"] for row in payload["methods"]} == {"upi", "card", "wallet", "netbanking"}


def test_dealer_portal_campaigns_are_data_driven(
    client: TestClient,
    session: Session,
):
    dealer_user = _create_customer(session)
    client.app.dependency_overrides[deps.get_current_user] = lambda: dealer_user

    dealer = _create_dealer_profile(session, dealer_user)
    now = datetime.now(UTC)

    active = DealerPromotion(
        dealer_id=dealer.id,
        name="Active Promo",
        description="Active campaign",
        promo_code="ACTIVE50",
        discount_type="PERCENTAGE",
        discount_value=15.0,
        start_date=now - timedelta(days=2),
        end_date=now + timedelta(days=4),
        is_active=True,
        requires_approval=False,
        approved_at=now - timedelta(days=3),
    )
    scheduled = DealerPromotion(
        dealer_id=dealer.id,
        name="Scheduled Promo",
        description="Future campaign",
        promo_code="SCHED20",
        discount_type="FIXED_AMOUNT",
        discount_value=20.0,
        start_date=now + timedelta(days=3),
        end_date=now + timedelta(days=7),
        is_active=True,
        requires_approval=False,
        approved_at=now,
    )
    expired = DealerPromotion(
        dealer_id=dealer.id,
        name="Expired Promo",
        description="Past campaign",
        promo_code="OLD10",
        discount_type="PERCENTAGE",
        discount_value=10.0,
        start_date=now - timedelta(days=10),
        end_date=now - timedelta(days=2),
        is_active=True,
        requires_approval=False,
        approved_at=now - timedelta(days=12),
    )
    paused = DealerPromotion(
        dealer_id=dealer.id,
        name="Paused Promo",
        description="Paused campaign",
        promo_code="PAUSE30",
        discount_type="FIXED_AMOUNT",
        discount_value=30.0,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=5),
        is_active=False,
        requires_approval=False,
        approved_at=now - timedelta(days=2),
    )
    pending = DealerPromotion(
        dealer_id=dealer.id,
        name="Pending Approval Promo",
        description="Awaiting approval",
        promo_code="PEND12",
        discount_type="PERCENTAGE",
        discount_value=12.0,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=8),
        is_active=True,
        requires_approval=True,
        approved_at=None,
    )
    session.add(active)
    session.add(scheduled)
    session.add(expired)
    session.add(paused)
    session.add(pending)
    session.commit()
    session.refresh(active)
    session.refresh(paused)

    usage_a = PromotionUsage(
        promotion_id=active.id,
        user_id=dealer_user.id,
        discount_applied=30.0,
        original_amount=220.0,
        final_amount=190.0,
        used_at=now - timedelta(hours=2),
    )
    usage_b = PromotionUsage(
        promotion_id=active.id,
        user_id=dealer_user.id,
        discount_applied=20.0,
        original_amount=130.0,
        final_amount=110.0,
        used_at=now - timedelta(hours=1),
    )
    usage_c = PromotionUsage(
        promotion_id=paused.id,
        user_id=dealer_user.id,
        discount_applied=10.0,
        original_amount=90.0,
        final_amount=80.0,
        used_at=now - timedelta(hours=3),
    )
    session.add(usage_a)
    session.add(usage_b)
    session.add(usage_c)
    session.commit()

    response = client.get("/api/v1/dealer/portal/campaigns")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5

    by_code = {row["promo_code"]: row for row in payload["data"]}
    assert by_code["ACTIVE50"]["status"] == "Active"
    assert by_code["SCHED20"]["status"] == "Scheduled"
    assert by_code["OLD10"]["status"] == "Expired"
    assert by_code["PAUSE30"]["status"] == "Paused"
    assert by_code["PEND12"]["status"] == "Pending Approval"

    assert by_code["ACTIVE50"]["redemptions"] == 2
    assert by_code["ACTIVE50"]["revenue"] == pytest.approx(300.0)
    assert by_code["PAUSE30"]["redemptions"] == 1
    assert by_code["PAUSE30"]["revenue"] == pytest.approx(80.0)

    summary = payload["summary"]
    assert summary["active_campaigns"] == 1
    assert summary["scheduled_campaigns"] == 1
    assert summary["expired_campaigns"] == 1
    assert summary["paused_campaigns"] == 1
    assert summary["pending_approval_campaigns"] == 1
    assert summary["total_redemptions"] == 3
    assert summary["total_revenue"] == pytest.approx(380.0)
    assert summary["total_discount_given"] == pytest.approx(60.0)
