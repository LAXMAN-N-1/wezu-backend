import requests
import json
import time
from datetime import datetime, timedelta
from sqlmodel import Session, select, create_engine
from app.models.station import Station
from app.models.dealer import DealerProfile
from app.models.user import User
from app.core.config import settings

BASE_URL = "http://127.0.0.1:8001/api/v1"
ENGINE = create_engine(settings.DATABASE_URL)

def setup_test_data():
    print("Setting up test data...")
    with Session(ENGINE) as session:
        # 1. Get or create a dealer
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not user:
            print("Admin user not found, cannot proceed.")
            return None
        
        dealer = session.exec(select(DealerProfile).where(DealerProfile.user_id == user.id)).first()
        if not dealer:
             # Create a mock dealer profile
             dealer = DealerProfile(
                 user_id=user.id,
                 business_name="Test Dealer Corp",
                 contact_person="Test Manager",
                 contact_email="test@dealer.com",
                 contact_phone="1234567890",
                 address_line1="Test Street",
                 city="Test City",
                 state="Test State",
                 pincode="123456",
                 is_active=True
             )
             session.add(dealer)
             session.commit()
             session.refresh(dealer)
        
        # 2. Create a test station
        station = Station(
            name="Test Verification Station",
            address="Test Location",
            latitude=12.9716,
            longitude=77.5946,
            dealer_id=dealer.id,
            status="active",
            updated_at=datetime.utcnow() - timedelta(minutes=10) # Start as "old"
        )
        session.add(station)
        session.commit()
        session.refresh(station)
        print(f"Created Test Station ID: {station.id}")
        return station.id

def verify_flow(station_id):
    # 3. Send Heartbeat
    print(f"\nSending heartbeat for station {station_id}...")
    payload = {
        "station_id": station_id,
        "status": "online",
        "metrics": {"temp": 42.5, "power": 1500}
    }
    resp = requests.post(f"{BASE_URL}/iot/heartbeat", json=payload)
    print(f"Heartbeat Response: {resp.status_code} - {resp.json().get('message')}")
    
    # 4. Check Station Status
    with Session(ENGINE) as session:
        station = session.get(Station, station_id)
        print(f"Station Status after heartbeat: {station.status}")
        print(f"Station Last Seen: {station.updated_at}")
    
    # 5. Check Admin Health Dashboard (Requires Auth - we'll just check the DB metrics instead or try auth if we have it)
    # For this verification, we'll check the StationHeartbeat table
    from app.models.station_heartbeat import StationHeartbeat
    with Session(ENGINE) as session:
        hb = session.exec(select(StationHeartbeat).where(StationHeartbeat.station_id == station_id)).first()
        if hb:
            print(f"StationHeartbeat record found! Metrics: {hb.metrics}")
        else:
            print("STATION_HEARTBEAT RECORD NOT FOUND!")

    # 6. Test Offline Detection
    print("\nSimulating 6 minutes of inactivity...")
    with Session(ENGINE) as session:
        station = session.get(Station, station_id)
        station.updated_at = datetime.utcnow() - timedelta(minutes=6)
        session.add(station)
        session.commit()
    
    print("Running monitor_stations task manually...")
    from app.tasks.station_monitor import monitor_stations
    monitor_stations()
    
    # 7. Final Verification
    with Session(ENGINE) as session:
        station = session.get(Station, station_id)
        print(f"Station Status after monitoring: {station.status}")
        
        from app.models.alert import Alert
        alert = session.exec(select(Alert).where(Alert.station_id == station_id).order_by(Alert.created_at.desc())).first()
        if alert:
            print(f"Alert Generated: {alert.alert_type} - {alert.message}")
        else:
            print("ALERT NOT GENERATED!")

if __name__ == "__main__":
    sid = setup_test_data()
    if sid:
        verify_flow(sid)
