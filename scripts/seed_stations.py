"""
WEZU Station Seeder — Five Locations (Hyderabad)
Seeds 5 operational stations across Hyderabad for testing.
Each station comes with a full set of slots.

Run: python scripts/seed_five_stations.py
"""

import os
import sys
import random
from datetime import datetime, UTC, timedelta

# Ensure parent directory is in sys.path for app imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import app.models.all # Force load all models
from sqlmodel import Session, select, func
from sqlalchemy import text
from app.db.session import engine
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot, StationStatus
from app.core.security import get_password_hash

# Config
SEED_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "Wezu@2026!Seed")
NOW = datetime.now(UTC)

STATION_LOCATIONS = [
    {
        "name": "Madhapur Tech-Hub Station",
        "address": "Opposite Cyber Towers, Hitech City",
        "city": "Hyderabad",
        "latitude": 17.4483,
        "longitude": 78.3915,
        "total_slots": 24,
        "is_24x7": True,
        "contact_phone": "+91 90000 10001"
    },
    {
        "name": "Gachibowli Financial Hub",
        "address": "Near DLF Cyber City, Gachibowli",
        "city": "Hyderabad",
        "latitude": 17.4401,
        "longitude": 78.3489,
        "total_slots": 32,
        "is_24x7": True,
        "contact_phone": "+91 90000 10002"
    },
    {
        "name": "Kondapur Green Plaza",
        "address": "Main Road, Kondapur Junction",
        "city": "Hyderabad",
        "latitude": 17.4622,
        "longitude": 78.3568,
        "total_slots": 16,
        "is_24x7": False,
        "contact_phone": "+91 90000 10003"
    },
    {
        "name": "Banjara Hills Premium",
        "address": "Road No. 12, Near Omega Hospital",
        "city": "Hyderabad",
        "latitude": 17.4123,
        "longitude": 78.4320,
        "total_slots": 20,
        "is_24x7": True,
        "contact_phone": "+91 90000 10004"
    },
    {
        "name": "Jubilee Hills Metro Point",
        "address": "Road No. 36, Jubilee Hills Metro Station",
        "city": "Hyderabad",
        "latitude": 17.4299,
        "longitude": 78.4127,
        "total_slots": 40,
        "is_24x7": True,
        "contact_phone": "+91 90000 10005"
    }
]

def seed_stations():
    print("Starting Station Seeding...")
    
    with Session(engine) as db:
        # 1. Ensure a Dealer exists to own these stations
        dealer_user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if not dealer_user:
            print("Creating default dealer user...")
            dealer_user = User(
                email="dealer@wezu.com",
                phone_number="8888888888",
                full_name="Laxman Kumar",
                hashed_password=get_password_hash(SEED_PASSWORD),
                user_type=UserType.DEALER,
                status=UserStatus.ACTIVE,
            )
            db.add(dealer_user)
            db.commit()
            db.refresh(dealer_user)
        
        dealer_profile = db.exec(select(DealerProfile).where(DealerProfile.user_id == dealer_user.id)).first()
        if not dealer_profile:
            print("Creating default dealer profile...")
            dealer_profile = DealerProfile(
                user_id=dealer_user.id,
                business_name="Laxman Energy Solutions",
                contact_person="Laxman Kumar",
                contact_email="dealer@wezu.com",
                contact_phone="8888888888",
                address_line1="Plot 42, Hitech City",
                city="Hyderabad",
                state="Telangana",
                pincode="500081",
                is_active=True,
            )
            db.add(dealer_profile)
            db.commit()
            db.refresh(dealer_profile)

        # 2. Create Stations
        for loc in STATION_LOCATIONS:
            # Check if station already exists
            existing_station = db.exec(select(Station).where(Station.name == loc["name"])).first()
            if existing_station:
                print(f"Station '{loc['name']}' already exists. Skipping.")
                continue
            
            print(f"Adding station: {loc['name']}...")
            station = Station(
                name=loc["name"],
                address=loc["address"],
                city=loc["city"],
                latitude=loc["latitude"],
                longitude=loc["longitude"],
                station_type="automated",
                total_slots=loc["total_slots"],
                status=StationStatus.OPERATIONAL,
                is_24x7=loc["is_24x7"],
                rating=round(random.uniform(4.0, 5.0), 1),
                dealer_id=dealer_profile.id,
                available_batteries=0,
                available_slots=loc["total_slots"],
                contact_phone=loc["contact_phone"],
                operating_hours='{"monday":"00:00-23:59","tuesday":"00:00-23:59","wednesday":"00:00-23:59","thursday":"00:00-23:59","friday":"00:00-23:59","saturday":"00:00-23:59","sunday":"00:00-23:59"}' if loc["is_24x7"] else '{"monday":"08:00-22:00","tuesday":"08:00-22:00","wednesday":"08:00-22:00","thursday":"08:00-22:00","friday":"08:00-22:00","saturday":"08:00-22:00","sunday":"08:00-22:00"}',
                last_heartbeat=NOW,
                last_maintenance_date=NOW - timedelta(days=random.randint(1, 30))
            )
            db.add(station)
            db.commit()
            db.refresh(station)
            
            # 3. Create Slots for the station (using raw SQL to avoid type cast issues with battery_id nulls)
            print(f"  -> Creating {loc['total_slots']} slots for {loc['name']}...")
            for si in range(loc["total_slots"]):
                db.execute(
                    text("INSERT INTO station_slots (station_id, slot_number, status, is_locked, current_power_w) "
                         "VALUES (:sid, :snum, :status, :locked, :pwr)"),
                    {"sid": station.id, "snum": si + 1, "status": "empty", "locked": True, "pwr": 0.0}
                )
            db.commit()
            
        print("\nSeeding complete! 5 stations added/verified.")

if __name__ == "__main__":
    seed_stations()
