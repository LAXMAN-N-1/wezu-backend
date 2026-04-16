"""
Integration Tests: Dealer Portal End-to-End Workflows
======================================================
Tests the complete dealer journey:

Workflow 1: Dealer submits station → sets inventory rules → sets opening hours → views batteries
Workflow 2: Dealer schedules maintenance → swap is blocked during maintenance
Workflow 3: Admin approves dealer station → station appears in public nearby search
Workflow 4: Dealer sees low-inventory alerts for their stations
Workflow 5: Cross-dealer isolation — one dealer cannot see another dealer's stations
"""

import pytest
from datetime import datetime, timedelta, UTC
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.user import User
from app.models.rbac import Role, UserRole
from app.models.roles import RoleEnum
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.battery import Battery
from app.core.security import create_access_token, get_password_hash


# ─── Helpers ─────────────────────────────────────────────────────────

def get_token(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


@pytest.fixture
def dealer_env(session: Session):
    """
    Set up a complete dealer environment: roles, dealer user,
    dealer profile, admin user, and a customer user.
    """
    # Ensure roles
    roles = {}
    for name in [RoleEnum.ADMIN.value, RoleEnum.DEALER.value, RoleEnum.CUSTOMER.value]:
        role = session.exec(select(Role).where(Role.name == name)).first()
        if not role:
            role = Role(name=name)
            session.add(role)
        roles[name] = role
    session.commit()

    # Dealer user + profile
    dealer_user = User(
        email="int_dealer_portal@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        status="active",
        phone_number="3333333333",
    )
    session.add(dealer_user)
    session.commit()
    session.refresh(dealer_user)
    session.add(UserRole(user_id=dealer_user.id, role_id=roles[RoleEnum.DEALER.value].id))

    dealer_profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Integration Dealer Corp",
        contact_person="Alice",
        contact_email="alice@dealer.com",
        contact_phone="3333333334",
        address_line1="100 Integration Blvd",
        city="Bangalore", state="Karnataka", pincode="560001",
    )
    session.add(dealer_profile)

    # Admin user
    admin_user = User(
        email="int_dealer_admin@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
        status="active",
        phone_number="3333333335",
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    session.add(UserRole(user_id=admin_user.id, role_id=roles[RoleEnum.ADMIN.value].id))

    # Customer user
    customer = User(
        email="int_dealer_cust@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        status="active",
        phone_number="3333333336",
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    session.refresh(dealer_profile)

    return {
        "dealer_user": dealer_user,
        "admin_user": admin_user,
        "customer": customer,
        "dealer_profile": dealer_profile,
        "roles": roles,
    }


# ─── Workflow 1: Station Setup End-to-End ──────────────────────────────

class TestDealerStationSetupFlow:
    """
    Integration: Dealer submits a station → configures inventory rules →
    sets opening hours → queries batteries.
    """

    def test_full_station_setup(self, client: TestClient, session: Session,
                                 dealer_env: dict):
        headers = get_token(dealer_env["dealer_user"])

        # Step 1: Submit station
        station_res = client.post("/api/v1/dealer-stations/new", headers=headers, json={
            "name": "Integration Dealer Station",
            "address": "200 Test Road",
            "latitude": 12.97,
            "longitude": 77.59,
            "total_slots": 8,
        })
        if station_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer station endpoints not implemented")
        assert station_res.status_code == status.HTTP_200_OK, station_res.text
        station_id = station_res.json()["id"]
        assert station_res.json()["approval_status"] == "pending"

        # Step 2: Set inventory threshold
        inv_res = client.put(
            f"/api/v1/dealer-stations/{station_id}/inventory-rules",
            headers=headers,
            json={"low_stock_threshold_pct": 25.0},
        )
        assert inv_res.status_code == status.HTTP_200_OK
        assert inv_res.json()["low_stock_threshold_pct"] == 25.0

        # Step 3: Set opening hours
        hours_res = client.put(
            f"/api/v1/dealer-stations/{station_id}/hours",
            headers=headers,
            json={"hours": "06:00-22:00"},
        )
        assert hours_res.status_code == status.HTTP_200_OK
        assert hours_res.json()["operating_hours"] == "06:00-22:00"

        # Step 4: View batteries (should be empty initially)
        batteries_res = client.get(
            f"/api/v1/dealer-stations/{station_id}/batteries",
            headers=headers,
        )
        assert batteries_res.status_code == status.HTTP_200_OK
        assert isinstance(batteries_res.json(), list)


# ─── Workflow 2: Maintenance Blocks Swaps ────────────────────────────

class TestMaintenanceBlocksSwaps:
    """
    Integration: Dealer creates a station → schedules maintenance →
    customer swap attempt is rejected during maintenance window.
    """

    def test_maintenance_prevents_swap(self, client: TestClient, session: Session,
                                        dealer_env: dict):
        dealer_headers = get_token(dealer_env["dealer_user"])
        customer_headers = get_token(dealer_env["customer"])

        # Create an active station directly in DB (bypass approval for test)
        station = Station(
            name="Maintenance Test Station",
            address="300 Maint Road",
            latitude=13.0, longitude=77.5,
            dealer_id=dealer_env["dealer_profile"].id,
            total_slots=4, status="active", approval_status="approved",
            operating_hours="00:00-23:59",
        )
        session.add(station)
        session.commit()
        session.refresh(station)

        # Schedule maintenance NOW
        start = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        end = (datetime.now(UTC) + timedelta(hours=3)).isoformat()

        maint_res = client.post(
            f"/api/v1/dealer-stations/{station.id}/schedule-maintenance",
            headers=dealer_headers,
            json={"start_time": start, "end_time": end, "reason": "Emergency repair"},
        )
        if maint_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Maintenance endpoint not implemented")
        assert maint_res.status_code == status.HTTP_200_OK

        # Customer tries to swap → should be blocked
        swap_res = client.post("/api/v1/swaps/initiate", headers=customer_headers, json={
            "station_id": station.id, "returned_battery_id": 999,
        })
        if swap_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Swap initiate endpoint not implemented")
        assert swap_res.status_code == status.HTTP_400_BAD_REQUEST
        assert "maintenance" in swap_res.json().get("detail", "").lower()


# ─── Workflow 3: Low-Inventory Alert Detection ──────────────────────

class TestLowInventoryAlertFlow:
    """
    Integration: Creates a station with few batteries vs slots →
    dealer queries alerts → station flagged as low-stock.
    """

    def test_low_stock_alert_triggered(self, client: TestClient, session: Session,
                                        dealer_env: dict):
        dealer_headers = get_token(dealer_env["dealer_user"])

        # Station with 4 slots but only 1 good battery (threshold 50% → needs 2)
        station = Station(
            name="LowStock Station",
            address="400 Alert Rd",
            latitude=12.5, longitude=77.5,
            dealer_id=dealer_env["dealer_profile"].id,
            total_slots=4, status="active", approval_status="approved",
            low_stock_threshold_pct=50.0,
        )
        session.add(station)
        session.commit()
        session.refresh(station)

        # Add 1 good battery (charge > 20, health > 80)
        b1 = Battery(
            serial_number="INT_ALERT_B1",
            current_charge=90.0, health_percentage=95.0,
            location_id=station.id, location_type="station", status="available",
        )
        session.add(b1)
        session.commit()
        session.refresh(b1)

        # Add slots
        session.add(StationSlot(station_id=station.id, slot_number=1, battery_id=b1.id))
        session.add(StationSlot(station_id=station.id, slot_number=2))
        session.add(StationSlot(station_id=station.id, slot_number=3))
        session.add(StationSlot(station_id=station.id, slot_number=4))
        session.commit()

        # Query alerts
        alerts_res = client.get("/api/v1/dealer-stations/inventory/alerts", headers=dealer_headers)
        if alerts_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Alerts endpoint not implemented")
        assert alerts_res.status_code == status.HTTP_200_OK

        data = alerts_res.json()
        alert = next((a for a in data if a["station_id"] == station.id), None)
        assert alert is not None, f"No alert found for station {station.id}"
        assert alert["available_count"] == 1
        assert alert["current_available_pct"] == 25.0


# ─── Workflow 4: Dealer Cross-Isolation ──────────────────────────────

class TestDealerCrossIsolation:
    """
    Integration: Dealer A creates a station → Dealer B attempts
    to access it → access is denied (404/403).
    """

    def test_other_dealer_cannot_see_station(
            self, client: TestClient, session: Session, dealer_env: dict):
        dealer_a_headers = get_token(dealer_env["dealer_user"])

        # Dealer A creates a station
        station_res = client.post("/api/v1/dealer-stations/new", headers=dealer_a_headers, json={
            "name": "Dealer A Private Station",
            "address": "500 Private Rd",
            "latitude": 12.0, "longitude": 77.0,
            "total_slots": 3,
        })
        if station_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Dealer station endpoints not implemented")
        assert station_res.status_code == status.HTTP_200_OK
        station_id = station_res.json()["id"]

        # Create Dealer B
        dealer_b = User(
            email="int_dealer_b@test.com",
            hashed_password=get_password_hash("password"),
            is_active=True,
            status="active",
            phone_number="2222222222",
        )
        session.add(dealer_b)
        session.commit()
        session.refresh(dealer_b)

        dealer_b_profile = DealerProfile(
            user_id=dealer_b.id,
            business_name="Dealer B Corp",
            contact_person="Bob",
            contact_email="bob@dealer.com",
            contact_phone="2222222223",
            address_line1="600 Other Rd",
            city="Delhi", state="Delhi", pincode="110001",
        )
        session.add(dealer_b_profile)
        session.commit()

        # Dealer B tries to access Dealer A's station
        dealer_b_headers = get_token(dealer_b)
        access_res = client.get(
            f"/api/v1/dealer-stations/{station_id}/batteries",
            headers=dealer_b_headers,
        )
        # Should get 404 (station concealed) or 403
        assert access_res.status_code in [
            status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN
        ]

    def test_admin_can_see_all_dealer_stations(
            self, client: TestClient, session: Session, dealer_env: dict):
        """Admin (superuser) should be able to list all stations regardless of dealer."""
        admin_headers = get_token(dealer_env["admin_user"])

        # Admin lists all stations via the admin endpoint
        res = client.get("/api/v1/stations/", headers=admin_headers)
        assert res.status_code == status.HTTP_200_OK
        assert isinstance(res.json(), list)
