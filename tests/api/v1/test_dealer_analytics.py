import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.swap import SwapSession
from app.models.battery import Battery


# ─── Fixtures ───

@pytest.fixture
def dealer_env(session: Session):
    """Create dealer user, DealerProfile, station, batteries, and swaps."""
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
    dealer_user = session.exec(select(User).where(User.email == "analytics_dealer@test.com")).first()
    if not dealer_user:
        dealer_user = User(
            email="analytics_dealer@test.com", hashed_password="pw",
            is_active=True, status="active",
        )
        session.add(dealer_user)
        session.commit()
        session.refresh(dealer_user)
        session.add(UserRole(user_id=dealer_user.id, role_id=dealer_role.id))
        session.commit()

    # Admin user
    admin_user = session.exec(select(User).where(User.email == "analytics_admin@test.com")).first()
    if not admin_user:
        admin_user = User(
            email="analytics_admin@test.com", hashed_password="pw",
            is_active=True, is_superuser=True, status="active",
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
        session.commit()

    # Dealer profile
    dealer_profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Test Dealer Co",
        contact_person="John",
        contact_email="john@test.com",
        contact_phone="9876543210",
        address_line1="123 Main St",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
    )
    session.add(dealer_profile)
    session.commit()
    session.refresh(dealer_profile)

    # Station
    station = Station(
        name="Test Station Alpha",
        address="456 Market St",
        latitude=19.076,
        longitude=72.877,
        dealer_id=dealer_profile.id,
        total_slots=10,
        rating=4.2,
        status="active",
    )
    session.add(station)
    session.commit()
    session.refresh(station)

    # Battery + slot
    battery = Battery(model="TestBattery", serial_number="TB001", status="available")
    session.add(battery)
    session.commit()
    session.refresh(battery)

    slot = StationSlot(station_id=station.id, slot_number=1, status="ready", battery_id=battery.id)
    session.add(slot)
    session.commit()

    # Create swap sessions — various users
    customer1 = session.exec(select(User).where(User.email == "cust1_da@test.com")).first()
    if not customer1:
        customer1 = User(email="cust1_da@test.com", hashed_password="pw", is_active=True, status="active")
        session.add(customer1)
    
    customer2 = session.exec(select(User).where(User.email == "cust2_da@test.com")).first()
    if not customer2:
        customer2 = User(email="cust2_da@test.com", hashed_password="pw", is_active=True, status="active")
        session.add(customer2)

    session.commit()
    session.refresh(customer1)
    session.refresh(customer2)

    now = datetime.utcnow()
    swaps = [
        SwapSession(user_id=customer1.id, station_id=station.id, swap_amount=100.0,
                     status="completed", created_at=now),
        SwapSession(user_id=customer1.id, station_id=station.id, swap_amount=120.0,
                     status="completed", created_at=now - timedelta(hours=2)),
        SwapSession(user_id=customer2.id, station_id=station.id, swap_amount=80.0,
                     status="completed", created_at=now - timedelta(days=1)),
        SwapSession(user_id=customer1.id, station_id=station.id, swap_amount=150.0,
                     status="completed", created_at=now - timedelta(days=15)),
    ]
    for s in swaps:
        session.add(s)
    session.commit()

    return {
        "dealer_user": dealer_user,
        "admin_user": admin_user,
        "dealer_profile": dealer_profile,
        "station": station,
    }


def get_token(user: User):
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


# ─── Overview ───

class TestOverview:
    def test_overview_returns_metrics(self, client, session, dealer_env):
        """#1: Overview has swap counts, revenue, rating."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "swaps_today" in data
        assert "swaps_month" in data
        assert "revenue_month" in data
        assert "avg_rating" in data
        assert "active_batteries" in data
        assert "station_count" in data

    def test_overview_swap_count_today(self, client, session, dealer_env):
        """#2: Today's swap count is correct (at least 2)."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/overview", headers=headers)
        data = resp.json()
        assert data["swaps_today"] >= 2

    def test_overview_rating_range(self, client, session, dealer_env):
        """#14: Rating is 0-5 range."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/overview", headers=headers)
        rating = resp.json()["avg_rating"]
        assert 0 <= rating <= 5


# ─── Trends ───

class TestTrends:
    def test_trends_daily(self, client, session, dealer_env):
        """#3: Daily trend returns list with revenue/swaps."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/trends?period=daily&periods=7", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 7
        assert "swaps" in data[0]
        assert "revenue" in data[0]

    def test_trends_monthly(self, client, session, dealer_env):
        """#4: Monthly trend works."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/trends?period=monthly&periods=3", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_trends_with_period_filter(self, client, session, dealer_env):
        """#13: Weekly filter works."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/trends?period=weekly&periods=4", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 4


# ─── Station Metrics ───

class TestStationMetrics:
    def test_station_metrics(self, client, session, dealer_env):
        """#5: Per-station list returned."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/stations", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["station_name"] == "Test Station Alpha"

    def test_station_utilization(self, client, session, dealer_env):
        """#6: Utilization % present."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/stations", headers=headers)
        station = resp.json()[0]
        assert "utilization_pct" in station
        assert station["utilization_pct"] >= 0


# ─── Customer Insights ───

class TestCustomerInsights:
    def test_customer_insights(self, client, session, dealer_env):
        """#7: Repeat %, CLV, churn returned."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/customers", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "repeat_customer_pct" in data
        assert "avg_customer_lifetime_value" in data
        assert "churn_rate_pct" in data
        assert "total_unique_customers" in data

    def test_customer_insights_percentages(self, client, session, dealer_env):
        """#15: Percentages in 0-100 range."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/customers", headers=headers)
        data = resp.json()
        assert 0 <= data["repeat_customer_pct"] <= 100
        assert 0 <= data["churn_rate_pct"] <= 100


# ─── Peak Hours ───

class TestPeakHours:
    def test_peak_hours(self, client, session, dealer_env):
        """#8: 24-hour distribution returned."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/peak-hours", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 24
        assert data[0]["hour"] == 0
        assert data[23]["hour"] == 23


# ─── Export ───

class TestExport:
    def test_export_csv(self, client, session, dealer_env):
        """#9: CSV download works."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/export/csv", headers=headers)
        assert resp.status_code == 200
        assert "swaps_today" in resp.text

    def test_export_json(self, client, session, dealer_env):
        """#10: JSON download works."""
        headers = get_token(dealer_env["dealer_user"])
        resp = client.get("/api/v1/dealer-analytics/export/json", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["station_count"] >= 1


# ─── RBAC ───

class TestRBAC:
    def test_non_dealer_denied(self, client, session, dealer_env):
        """#11: Admin (non-dealer) gets 403."""
        headers = get_token(dealer_env["admin_user"])
        resp = client.get("/api/v1/dealer-analytics/overview", headers=headers)
        assert resp.status_code == 403

    def test_unauthenticated_denied(self, client, session, dealer_env):
        """#12: No token gets 401."""
        resp = client.get("/api/v1/dealer-analytics/overview")
        assert resp.status_code == 401
