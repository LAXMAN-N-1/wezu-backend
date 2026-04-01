import sys
import os
import random
from datetime import datetime, UTC, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import app.main # Fixes SQLAlchemy mapper initialization order

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User

from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental
from app.models.support import SupportTicket
from app.models.dealer import DealerProfile
from app.core.security import get_password_hash

def seed_analytics_data():
    with Session(engine) as session:
        print("Starting Analytics Data Seeding...")

        # 1. Create Users
        print("Creating Users...")
        users = []
        for i in range(50):
            email = f"user{i}@example.com"
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                created_days_ago = random.randint(0, 60)
                user = User(
                    email=email,
                    full_name=f"Test User {i}",
                    hashed_password=get_password_hash(os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")),
                    is_active=True,
                    created_at=datetime.now(UTC) - timedelta(days=created_days_ago) # Simulated creation date
                )
                session.add(user)
                session.flush()
            users.append(user)
        
        # 2. Create Stations
        print("Creating Stations...")
        stations = []
        station_names = ["Hyderabad Central", "Bangalore Koramangala", "Mumbai Andheri West", "Delhi Connaught Place", "Chennai T. Nagar"]
        for name in station_names:
            station = session.exec(select(Station).where(Station.name == name)).first()
            if not station:
                station = Station(
                    name=name,
                    address=f"{name} Address",
                    latitude=17.3850 + random.uniform(-0.1, 0.1),
                    longitude=78.4867 + random.uniform(-0.1, 0.1),
                    total_slots=20,
                    available_slots=random.randint(5, 15),
                    status="active", # Correct status string
                    is_active=True
                )
                session.add(station)
                session.flush()
            stations.append(station)

        # 3. Create Batteries
        print("Creating Batteries...")
        batteries = []
        for i in range(150):
            serial = f"BAT-ANA-{i}"
            battery = session.exec(select(Battery).where(Battery.serial_number == serial)).first()
            if not battery:
                battery = Battery(
                    serial_number=serial,
                    model="Li-Ion-2024",
                    capacity_ah=random.choice([2.5, 3.0, 5.0]),
                    status=random.choice(["available", "in_use", "charging", "maintenance"]),
                    current_charge=random.uniform(10.0, 100.0),
                    health_percentage=random.uniform(60.0, 100.0),
                    station_id=random.choice(stations).id if random.random() > 0.3 else None
                )
                session.add(battery)
                session.flush()
            batteries.append(battery)

        # 4. Create Rentals ( Historical & Active )
        print("Creating Rentals...")
        for i in range(300): # 300 rentals overall
            user = random.choice(users)
            battery = random.choice(batteries)
            station_start = random.choice(stations)
            
            # Simulate dates over the last 30 days
            days_ago = random.randint(0, 30)
            start_time = datetime.now(UTC) - timedelta(days=days_ago, hours=random.randint(1, 10))
            
            # 10% active, 90% completed
            is_active = random.random() < 0.1
            status = "active" if is_active else "completed"
            
            # Determine end time and price
            if status == "completed":
                duration_hours = random.uniform(0.5, 4.0)
                end_time = start_time + timedelta(hours=duration_hours)
                total_amount = round(duration_hours * 50.0, 2) # Example 50 per hour
            else:
                end_time = None
                total_amount = 0.0

            rental = Rental(
                user_id=user.id,
                battery_id=battery.id,
                start_station_id=station_start.id,
                drop_station_id=random.choice(stations).id if status == "completed" else None,
                start_time=start_time,
                end_time=end_time,
                status=status,
                total_amount=total_price
            )
            session.add(rental)

        # 5. Create Support Tickets
        print("Creating Support Tickets...")
        for i in range(30):
            user = random.choice(users)
            ticket = SupportTicket(
                user_id=user.id,
                subject=random.choice(["Battery issue", "Payment failed", "Station offline", "App crash"]),
                category=random.choice(["technical", "billing", "general"]),
                description="Sample randomly generated issue for analytics.",
                status=random.choice(["open", "in_progress", "resolved", "closed"])
            )
            session.add(ticket)

        # 6. Create Dealer Profiles
        print("Creating Dealer Profiles...")
        cities = ["Hyderabad", "Bangalore", "Mumbai", "Delhi", "Chennai"]
        states = ["Telangana", "Karnataka", "Maharashtra", "Delhi", "Tamil Nadu"]
        for i in range(10):
            user = random.choice(users)
            dealer = session.exec(select(DealerProfile).where(DealerProfile.user_id == user.id)).first()
            if not dealer:
                city = random.choice(cities)
                state = random.choice(states)
                dealer = DealerProfile(
                    user_id=user.id,
                    business_name=f"Dealer Business {i}",
                    contact_person=user.full_name or f"Contact {i}",
                    contact_email=f"dealer{i}@example.com",
                    contact_phone=f"9{random.randint(100000000, 999999999)}",
                    address_line1=f"{random.randint(1, 999)} Main Road",
                    city=city,
                    state=state,
                    pincode=str(random.randint(400001, 799999)),
                    gst_number=f"GSTIN{random.randint(1000,9999)}",
                    is_active=random.random() > 0.2  # 80% active
                )
                session.add(dealer)

        # Commit all
        session.commit()
        print("Analytics Data Seeding Complete!")

if __name__ == "__main__":
    seed_analytics_data()
