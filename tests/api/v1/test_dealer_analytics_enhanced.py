import pytest
from datetime import datetime, timedelta
from sqlmodel import select

from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.swap import SwapSession
from app.models.battery import Battery

def get_token(user: User):
    from app.core.security import create_access_token
    access_token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def analytics_test_env(session):
    # Dealer User
    dealer_user = User(email="testdealer.analytics@test.com", hashed_password="pw", status="active", is_active=True)
    session.add(dealer_user)
    session.commit()
    session.refresh(dealer_user)

    dealer_profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Test Dealer Analytics Co",
        contact_person="Alice",
        contact_email="testdealer.analytics@test.com",
        contact_phone="+1234567891",
        address_line1="456 Analytics Rd",
        city="Analytics City",
        state="AnState",
        pincode="654321"
    )
    session.add(dealer_profile)
    session.commit()
    session.refresh(dealer_profile)

    # Station
    station = Station(
        dealer_id=dealer_profile.id,
        name="Analytics Station 1",
        address="789 Station St",
        latitude=40.71,
        longitude=-74.00,
        total_slots=4,
        status="active"
    )
    session.add(station)
    session.commit()
    session.refresh(station)

    # Battery
    b1 = Battery(serial_number="ANALYTICS_BAT_1", current_charge=100.0, health_percentage=90.0, location_id=station.id, location_type="station", status="available")
    b2 = Battery(serial_number="ANALYTICS_BAT_2", current_charge=50.0, health_percentage=80.0, location_id=station.id, location_type="station", status="available")
    session.add_all([b1, b2])
    session.commit()
    session.refresh(b1)
    session.refresh(b2)

    s1 = StationSlot(station_id=station.id, slot_number=1, battery_id=b1.id)
    s2 = StationSlot(station_id=station.id, slot_number=2, battery_id=b2.id)
    session.add_all([s1, s2])
    session.commit()

    # Customer 1 - Promoter
    cust1 = User(email="cust1.analytics@test.com", hashed_password="pw", status="active", is_active=True)
    session.add(cust1)
    session.commit()

    # Customer 2 - Detractor
    cust2 = User(email="cust2.analytics@test.com", hashed_password="pw", status="active", is_active=True)
    session.add(cust2)
    session.commit()

    # Swaps
    # Promoter swap
    swap1 = SwapSession(
        user_id=cust1.id,
        station_id=station.id,
        old_battery_id=None,
        new_battery_id=b1.id,
        amount=5.0,
        status="completed",
        created_at=datetime.utcnow() - timedelta(days=1)
    )
    # Average swap
    swap2 = SwapSession(
        user_id=cust1.id,
        station_id=station.id,
        old_battery_id=b1.id,
        new_battery_id=b2.id,
        amount=5.0,
        status="completed",
        created_at=datetime.utcnow() - timedelta(days=2)
    )
    # Detractor swap
    swap3 = SwapSession(
        user_id=cust2.id,
        station_id=station.id,
        old_battery_id=b2.id,
        new_battery_id=b1.id,
        amount=10.0,
        status="completed",
        created_at=datetime.utcnow() - timedelta(days=3)
    )
    session.add_all([swap1, swap2, swap3])

    from app.models.review import Review
    rev1 = Review(user_id=cust1.id, station_id=station.id, rating=5)
    rev2 = Review(user_id=cust1.id, station_id=station.id, rating=4)
    rev3 = Review(user_id=cust2.id, station_id=station.id, rating=1)
    session.add_all([rev1, rev2, rev3])

    session.commit()

    return {
        "dealer_user": dealer_user,
        "dealer_profile": dealer_profile,
        "station": station
    }

def test_rating_distribution(client, session, analytics_test_env):
    """Test Overview includes 5-star distribution."""
    headers = get_token(analytics_test_env["dealer_user"])
    resp = client.get("/api/v1/dealer-analytics/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "rating_distribution" in data
    dist = data["rating_distribution"]
    assert dist["5"] == 1
    assert dist["4"] == 1
    assert dist["3"] == 0
    assert dist["2"] == 0
    assert dist["1"] == 1

def test_station_health_score(client, session, analytics_test_env):
    """Test stations array includes health score based on batteries."""
    headers = get_token(analytics_test_env["dealer_user"])
    resp = client.get("/api/v1/dealer-analytics/stations", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 1
    station_metrics = data[0]
    assert "health_score_pct" in station_metrics
    # Avg of 90 and 80 is 85
    assert station_metrics["health_score_pct"] == 85.0

def test_nps_score_calculation(client, session, analytics_test_env):
    """Test NPS accurately aggregates promoters minus detractors."""
    headers = get_token(analytics_test_env["dealer_user"])
    resp = client.get("/api/v1/dealer-analytics/customers", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "nps_score" in data
    # Total ratings: 3
    # Promoters: 2 (ratings 4 and 5)
    # Detractors: 1 (rating 1)
    # Passives: 0
    # % Promoters: (2/3) * 100 = 66.66%
    # % Detractors: (1/3) * 100 = 33.33%
    # NPS = 66.66 - 33.33 = 33.3%
    nps = data["nps_score"]
    assert 33.0 <= nps <= 34.0

def test_export_pdf(client, session, analytics_test_env):
    """Endpoint `/export/pdf` returns `application/pdf`."""
    headers = get_token(analytics_test_env["dealer_user"])
    resp = client.get("/api/v1/dealer-analytics/export/pdf", headers=headers)
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]

def test_email_report(client, session, analytics_test_env):
    """Endpoint triggers email send without errors."""
    headers = get_token(analytics_test_env["dealer_user"])
    resp = client.post("/api/v1/dealer-analytics/email-report", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["email"] == "testdealer.analytics@test.com"
