import pytest
from datetime import datetime, timedelta, time
from sqlmodel import Session, select

from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.battery import Battery


# ─── Fixtures ───

@pytest.fixture
def station_test_env(session: Session):
    """Setup roles, dealer user, customer user, and a dealer profile."""
    # Roles
    dealer_role = session.exec(select(Role).where(Role.name == RoleEnum.DEALER.value)).first()
    if not dealer_role:
        dealer_role = Role(name=RoleEnum.DEALER.value)
        session.add(dealer_role)

    admin_role = session.exec(select(Role).where(Role.name == RoleEnum.ADMIN.value)).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value)
        session.add(admin_role)
    session.commit()

    # Dealer user
    dealer_user = User(
        email="station_dealer@test.com", hashed_password="pw",
        is_active=True, status="active",
    )
    session.add(dealer_user)
    session.commit()
    session.refresh(dealer_user)
    session.add(UserRole(user_id=dealer_user.id, role_id=dealer_role.id))

    # Admin user
    admin_user = User(
        email="station_admin@test.com", hashed_password="pw",
        is_active=True, is_superuser=True, status="active",
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))

    # Customer user
    customer_user = User(
        email="station_cust@test.com", hashed_password="pw",
        is_active=True, status="active",
    )
    session.add(customer_user)
    session.commit()
    session.refresh(customer_user)

    # Dealer profile
    dealer_profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Station Dealer Co",
        contact_person="Jane",
        contact_email="jane@test.com",
        contact_phone="9876543211",
        address_line1="456 Station St",
        city="Delhi",
        state="Delhi",
        pincode="110001",
    )
    session.add(dealer_profile)
    session.commit()
    session.refresh(dealer_profile)

    return {
        "dealer_user": dealer_user,
        "admin_user": admin_user,
        "customer": customer_user,
        "dealer_profile": dealer_profile
    }

def get_token(user: User):
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


# ─── Tests: Station Submission & Config ───

class TestStationManagement:
    def test_submit_station(self, client, session, station_test_env):
        """#1: Creates station as 'pending'."""
        headers = get_token(station_test_env["dealer_user"])
        payload = {
            "name": "New Dealer Station",
            "address": "123 New Road",
            "latitude": 28.5,
            "longitude": 77.1,
            "total_slots": 10
        }
        resp = client.post("/api/v1/dealer-stations", headers=headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"]
        assert data["name"] == "New Dealer Station"
        assert data["approval_status"] == "pending"
        assert data["dealer_id"] == station_test_env["dealer_profile"].id

    def test_set_inventory_threshold(self, client, session, station_test_env):
        """#4: Updates low_stock_threshold_pct."""
        headers = get_token(station_test_env["dealer_user"])
        station_id = client.post("/api/v1/dealer-stations", headers=headers, json={
            "name": "D1 S1", "address": "X", "latitude": 0, "longitude": 0, "total_slots": 2
        }).json()["id"]

        resp = client.put(
            f"/api/v1/dealer-stations/{station_id}/inventory-rules",
            headers=headers,
            json={"low_stock_threshold_pct": 30.0}
        )
        assert resp.status_code == 200
        assert resp.json()["low_stock_threshold_pct"] == 30.0

    def test_update_hours(self, client, session, station_test_env):
        """#7: Modifies opening_hours."""
        headers = get_token(station_test_env["dealer_user"])
        station_id = client.post("/api/v1/dealer-stations", headers=headers, json={
            "name": "D1 S2", "address": "X", "latitude": 0, "longitude": 0, "total_slots": 2
        }).json()["id"]

        resp = client.put(
            f"/api/v1/dealer-stations/{station_id}/hours",
            headers=headers,
            json={"hours": "00:00-23:59"}
        )
        assert resp.status_code == 200
        assert resp.json()["opening_hours"] == "00:00-23:59"


# ─── Tests: Inventory & Alerts ───

class TestInventoryAlerts:
    @pytest.fixture(autouse=True)
    def setup_inventory(self, session, station_test_env):
        """Create an active station with slots and batteries."""
        station = Station(
            name="Inv Station", address="Inv Addr", latitude=0, longitude=0,
            dealer_id=station_test_env["dealer_profile"].id,
            total_slots=4, status="active", approval_status="approved",
            low_stock_threshold_pct=50.0 # 50% of 4 = 2. So if < 2 good batteries, alert!
        )
        session.add(station)
        session.commit()
        session.refresh(station)
        self.inv_station_id = station.id

        # Add 1 Good battery (>20 current_charge, >80 health), 1 Good battery (<20 current_charge), 1 Degraded (<80 health)
        b1 = Battery(serial_number="B1", current_charge=100.0, health_percentage=100.0, location_id=station.id, location_type="station", status="available")
        b2 = Battery(serial_number="B2", current_charge=15.0, health_percentage=100.0, location_id=station.id, location_type="station", status="charging")
        b3 = Battery(serial_number="B3", current_charge=100.0, health_percentage=70.0, location_id=station.id, location_type="station", status="available")
        session.add_all([b1, b2, b3])
        session.commit()

        # Add slots
        s1 = StationSlot(station_id=station.id, slot_number=1, battery_id=b1.id)
        s2 = StationSlot(station_id=station.id, slot_number=2, battery_id=b2.id)
        s3 = StationSlot(station_id=station.id, slot_number=3, battery_id=b3.id)
        s4 = StationSlot(station_id=station.id, slot_number=4) # Empty
        session.add_all([s1, s2, s3, s4])
        session.commit()

    def test_view_batteries(self, client, session, station_test_env):
        """#2: Returns batteries for a station."""
        headers = get_token(station_test_env["dealer_user"])
        resp = client.get(f"/api/v1/dealer-stations/{self.inv_station_id}/batteries", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_filter_batteries_health(self, client, session, station_test_env):
        """#3: Query parameter health_status works."""
        headers = get_token(station_test_env["dealer_user"])
        resp = client.get(f"/api/v1/dealer-stations/{self.inv_station_id}/batteries?health_status=degraded", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["serial_number"] == "B3"

    def test_fetch_alerts(self, client, session, station_test_env):
        """#5: Identifies stations below threshold."""
        # We set threshold to 50%. Total slots = 4. Needed = 2.
        # We only have 1 "ready" battery (B1 has SOC > 20 and is GOOD).
        # So 1/4 = 25% < 50%. It should trigger alert.
        headers = get_token(station_test_env["dealer_user"])
        resp = client.get("/api/v1/dealer-stations/alerts", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Find alert for inv_station
        alert = next((a for a in data if a["station_id"] == self.inv_station_id), None)
        assert alert is not None
        assert alert["available_count"] == 1
        assert alert["current_available_pct"] == 25.0


# ─── Tests: Maintenance & Enforcement ───

class TestMaintenanceEnforcement:
    @pytest.fixture(autouse=True)
    def setup_maintenance_station(self, session, station_test_env):
        """Create a station expressly for testing downtime/hours enforcement."""
        station = Station(
            name="Main Station", address="Main Addr", latitude=0, longitude=0,
            dealer_id=station_test_env["dealer_profile"].id,
            total_slots=4, status="active", approval_status="approved",
            opening_hours="09:00-18:00"
        )
        session.add(station)
        session.commit()
        session.refresh(station)
        self.m_station_id = station.id

    def test_schedule_maintenance(self, client, session, station_test_env):
        """#6: Creates StationDowntime."""
        headers = get_token(station_test_env["dealer_user"])
        start = (datetime.utcnow() + timedelta(days=1)).isoformat()
        end = (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat()
        
        payload = {
            "start_time": start,
            "end_time": end,
            "reason": "Routine Checkup"
        }
        resp = client.post(f"/api/v1/dealer-stations/{self.m_station_id}/maintenance", headers=headers, json=payload)
        assert resp.status_code == 200
        assert resp.json()["reason"] == "Routine Checkup"
        
        # Test Double booking prevent (#12)
        resp2 = client.post(f"/api/v1/dealer-stations/{self.m_station_id}/maintenance", headers=headers, json=payload)
        assert resp2.status_code == 400
        assert "overlaps" in resp2.json()["detail"]

    def test_maintenance_enforced(self, client, session, station_test_env):
        """#9: Swap fails if under maintenance."""
        # Setup hours to definitely be OPEN right now.
        open_str = "00:00"
        close_str = "23:59"
        
        dealer_headers = get_token(station_test_env["dealer_user"])
        client.put(f"/api/v1/dealer-stations/{self.m_station_id}/hours", headers=dealer_headers, json={"hours": f"{open_str}-{close_str}"})

        # 1. Schedule downtime NOW
        start = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        end = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        client.post(f"/api/v1/dealer-stations/{self.m_station_id}/maintenance", headers=dealer_headers, json={
            "start_time": start, "end_time": end, "reason": "Emergency Fix"
        })

        # 2. Try swap
        cust_headers = get_token(station_test_env["customer"])
        resp = client.post("/api/v1/swaps/initiate", headers=cust_headers, json={
            "station_id": self.m_station_id, "returned_battery_id": 999
        })
        assert resp.status_code == 400
        assert "maintenance" in resp.json()["detail"].lower()

    def test_hours_enforced(self, client, session, station_test_env):
        """#8: Swap fails if outside hours."""
        # Setup hours to definitely be closed right now.
        # If current UTC hour is H, set open to H+2 to H+3
        current_hour = datetime.utcnow().hour
        open_h = (current_hour + 2) % 24
        close_h = (current_hour + 3) % 24
        
        # Format string nicely
        open_str = f"{open_h:02d}:00"
        close_str = f"{close_h:02d}:00"
        
        dealer_headers = get_token(station_test_env["dealer_user"])
        client.put(f"/api/v1/dealer-stations/{self.m_station_id}/hours", headers=dealer_headers, json={"hours": f"{open_str}-{close_str}"})

        # Try swap
        cust_headers = get_token(station_test_env["customer"])
        resp = client.post("/api/v1/swaps/initiate", headers=cust_headers, json={
            "station_id": self.m_station_id, "returned_battery_id": 999
        })
        assert resp.status_code == 400
        assert "operating hours" in resp.json()["detail"].lower()

# ─── Tests: Edge Cases & Authorization ───

class TestEdgeCases:
    def test_non_dealer_denied(self, client, session, station_test_env):
        """#10: Admin/user cannot access dealer endpoints."""
        headers = get_token(station_test_env["admin_user"]) # Not a dealer profile
        resp = client.get("/api/v1/dealer-stations/alerts", headers=headers)
        assert resp.status_code == 403

    def test_missing_station_returns_404(self, client, session, station_test_env):
        """#11: 404 for non-existent station."""
        headers = get_token(station_test_env["dealer_user"])
        resp = client.get("/api/v1/dealer-stations/9999/batteries", headers=headers)
        assert resp.status_code == 404

    def test_different_dealer_station_denied(self, client, session, station_test_env):
        """#13: Dealer cannot view another dealer's station."""
        # Create station for dealer 1
        headers = get_token(station_test_env["dealer_user"])
        s_id = client.post("/api/v1/dealer-stations", headers=headers, json={
            "name": "D1 Station", "address": "X", "latitude": 0, "longitude": 0, "total_slots": 2
        }).json()["id"]

        # Create dealer 2
        d2 = User(email="d2@test.com", hashed_password="pw", status="active", is_active=True)
        session.add(d2)
        session.commit()
        session.refresh(d2)
        dp2 = DealerProfile(
            user_id=d2.id, business_name="D2", contact_person="John",
            contact_email="d2@t.com", contact_phone="+1234567890",
            address_line1="123 Road", city="City", state="State", pincode="123456"
        )
        session.add(dp2)
        session.commit()
        
        headers2 = get_token(d2)
        resp = client.get(f"/api/v1/dealer-stations/{s_id}/batteries", headers=headers2)
        assert resp.status_code == 404 # Concealed via 404 instead of 403.

    def test_rental_enforcement(self, client, session, station_test_env):
        """#14: Rentals also enforce hours/maintenance."""
        # Use a station that's closed
        m_station = session.exec(select(Station).where(Station.name == "Main Station")).first()
        if not m_station:
             m_station = Station(
                  name="Main Station", address="Main Addr", latitude=0, longitude=0,
                  dealer_id=station_test_env["dealer_profile"].id,
                  total_slots=4, status="active", approval_status="approved",
             )
        m_station.opening_hours = "01:00-01:01" # Guarantee closed
        session.add(m_station)
        session.commit()

        # Needs a battery for the rental payloads
        from app.models.battery import Battery
        b1 = Battery(serial_number="R1", current_charge=100.0, health_percentage=100.0, location_id=m_station.id, location_type="station", status="available")
        session.add(b1)
        session.commit()
        session.refresh(b1)

        cust_headers = get_token(station_test_env["customer"])
        resp = client.post("/api/v1/rentals/", headers=cust_headers, json={
            "pickup_station_id": m_station.id,
            "battery_id": b1.id,
            "duration_days": 2
        })
        assert resp.status_code == 400
        assert "operating hours" in resp.json()["detail"].lower()

    def test_invalid_hours_format_handled(self, client, session, station_test_env):
        """#15: Invalid hours format gracefully fallback to open."""
        m_station = session.exec(select(Station)).first()
        if not m_station:
             m_station = Station(
                  name="Main Station", address="Main Addr", latitude=0, longitude=0,
                  dealer_id=station_test_env["dealer_profile"].id,
                  total_slots=4, status="active", approval_status="approved",
             )
        m_station.opening_hours = "INVALID"
        session.add(m_station)
        session.commit()

        cust_headers = get_token(station_test_env["customer"])
        # Should not raise 400 due to hours, might fail for battery ID (404/others)
        resp = client.post("/api/v1/swaps/initiate", headers=cust_headers, json={
            "station_id": m_station.id, "returned_battery_id": 999
        })
        # If it's a 400, it shouldn't be about operating hours
        assert "operating hours" not in str(resp.json()).lower()

