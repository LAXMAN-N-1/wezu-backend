"""
Integration Tests: Battery Booking & Slot Reservation
=====================================================
Tests the real-time availability and locking mechanism for battery swaps.

Workflow 1: Inventory Search → Battery Reservation → Inventory Locking
Workflow 2: Reservation Expiry → Background Cleanup → Inventory Release
Workflow 3: Duplicate Reservation Prevention → User Limits → Active Status check
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, UTC, timedelta
import uuid

from app.models.user import User
from app.models.battery import Battery, BatteryStatus
from app.models.station import Station, StationSlot
from app.models.battery_reservation import BatteryReservation
from app.core.security import create_access_token

def get_token(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}

class TestBookingReservationFlow:

    @pytest.fixture
    def booking_env(self, session: Session):
        # 1. Dealer
        dealer = User(
            email=f"booking_dealer_{uuid.uuid4().hex[:8]}@wezu.com",
            user_type="dealer",
            is_active=True,
            phone_number=f"99{uuid.uuid4().hex[:8]}"
        )
        session.add(dealer)
        
        # 2. Station
        station = Station(
            name="Booking Hub",
            address="Booking Hub Address",
            dealer_id=dealer.id,
            is_operational=True,
            latitude=12.97,
            longitude=77.59,
            status="OPERATIONAL" 
        )
        session.add(station)
        session.commit()
        session.refresh(station)
        
        battery = Battery(
            serial_number=f"BATT-RES-{uuid.uuid4().hex[:6]}",
            status="available",
            station_id=station.id,
            location_id=station.id,
            location_type="station",
            current_charge=90.0
        )
        session.add(battery)
        session.commit()
        session.refresh(battery)

        # 4. Station Slot
        slot = StationSlot(
            station_id=station.id,
            slot_number=1,
            battery_id=battery.id,
            status="ready",
            is_locked=False
        )
        session.add(slot)
        session.commit()
        
        # 4. Customer (re-labeling as 5)
        customer = User(
            email=f"booking_customer_{uuid.uuid4().hex[:8]}@example.com",
            user_type="customer",
            is_active=True,
            phone_number=f"88{uuid.uuid4().hex[:8]}"
        )
        session.add(customer)
        session.commit()
        session.refresh(customer)
        
        return {
            "dealer": dealer,
            "station": station,
            "battery": battery,
            "customer": customer
        }

    def test_reservation_creation_and_blocking(self, client: TestClient, session: Session, booking_env: dict):
        customer = booking_env["customer"]
        station = booking_env["station"]
        headers = get_token(customer)
        
        # 1. Customer reserves a battery at the station
        booking_payload = {
            "station_id": station.id
        }
        create_res = client.post("/api/v1/bookings/", json=booking_payload, headers=headers)
        assert create_res.status_code == 200
        booking_data = create_res.json()
        assert booking_data["status"] == "PENDING"
        
        # 2. Verify another reservation is blocked (same user)
        res2 = client.post("/api/v1/bookings/", json=booking_payload, headers=headers)
        assert res2.status_code == 400
        assert "already has an active reservation" in res2.json()["error"]

        # 3. Verify detail retrieval
        booking_id = booking_data["id"]
        detail_res = client.get(f"/api/v1/bookings/{booking_id}", headers=headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["id"] == booking_id

    def test_reservation_cancellation(self, client: TestClient, session: Session, booking_env: dict):
        customer = booking_env["customer"]
        station = booking_env["station"]
        headers = get_token(customer)
        
        # 1. Create reservation
        create_res = client.post("/api/v1/bookings/", json={"station_id": station.id}, headers=headers)
        booking_id = create_res.json()["id"]
        
        # 2. Cancel it
        cancel_res = client.delete(f"/api/v1/bookings/{booking_id}", headers=headers)
        assert cancel_res.status_code == 200
        
        # 3. Verify status in DB
        session.refresh(session.get(BatteryReservation, booking_id))
        resv = session.get(BatteryReservation, booking_id)
        assert resv.status == "CANCELLED"

    def test_reservation_expiry_sim(self, client: TestClient, session: Session, booking_env: dict):
        # We simulate the expiry logic from BookingService
        customer = booking_env["customer"]
        station = booking_env["station"]
        battery = booking_env["battery"]
        
        # 1. Create an expired reservation in DB
        resv = BatteryReservation(
            user_id=customer.id,
            station_id=station.id,
            battery_id=battery.id,
            start_time=datetime.now(UTC) - timedelta(minutes=60),
            end_time=datetime.now(UTC) - timedelta(minutes=30),
            status="PENDING"
        )
        session.add(resv)
        session.commit()
        
        # 2. Normally a background task calls BookingService.release_expired_reservations(db)
        from app.services.booking_service import BookingService
        expired_count = BookingService.release_expired_reservations(session)
        assert expired_count >= 1
        
        # 3. Verify status
        session.refresh(resv)
        assert resv.status == "EXPIRED"
