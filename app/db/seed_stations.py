from __future__ import annotations
from datetime import datetime, timedelta
import random
from sqlmodel import Session, select
from app.db.session import engine
from app.models.station import Station, StationImage, StationSlot
from app.models.battery import Battery
from app.models.vendor import Vendor
from app.models.dealer import DealerProfile
from app.models.user import User
from app.models.staff import StaffProfile # Explicitly import missing models
from app.models.session import UserSession # Explicitly import missing models
from app.models.vendor import Vendor
from app.models.station import Station, StationImage, StationSlot
from app.models.battery import Battery

# Import all models to ensure SQLModel registry is populated
import app.models
from app.models import *

def seed_stations():
    with Session(engine) as session:
        # 1. Cleanup existing data to ensure a fresh, dynamic state
        print("Cleaning up existing station and rental data...")
        session.execute(text("DELETE FROM station_slots"))
        session.execute(text("DELETE FROM station_images"))
        session.execute(text("DELETE FROM rentals"))
        session.execute(text("DELETE FROM stations"))
        session.execute(text("DELETE FROM batteries"))
        session.commit()
        
        # 2. Ensure we have a vendor and a dealer
        vendor = session.exec(select(Vendor)).first()
        if not vendor:
            vendor = Vendor(
                name="Wezu Energy Solutions", 
                email="ops@wezu.com",
                phone="+919998887776",
                contact_email="ops@wezu.com"
            )
            session.add(vendor)
            session.commit()
            session.refresh(vendor)

        dealer = session.exec(select(DealerProfile)).first()
        if not dealer:
            user = session.exec(select(User)).first()
            if user:
                dealer = DealerProfile(
                    user_id=user.id, 
                    business_name="Elite Battery Dealers",
                    contact_person="Murari Kumar",
                    contact_email="murari@elite.com",
                    contact_phone="+919876543210",
                    address_line1="Jubilee Hills Checkpost",
                    city="Hyderabad",
                    state="Telangana",
                    pincode="500033"
                )
                session.add(dealer)
                session.commit()
                session.refresh(dealer)

        # 3. Define 20 Diverse Stations in Hyderabad
        areas = [
            ("Banjara Hills", 17.4156, 78.4447, ["Parking", "Coffee", "WIFI"]),
            ("Jubilee Hills", 17.4326, 78.4071, ["24/7", "Premium Lounge"]),
            ("Madhapur", 17.4483, 78.3915, ["Quick Swap", "WIFI"]),
            ("Gachibowli", 17.4401, 78.3489, ["Tech Support", "Parking"]),
            ("Kondapur", 17.4622, 78.3568, ["Solar Powered"]),
            ("Hitech City", 17.4435, 78.3772, ["Automated"]),
            ("Kukatpally", 17.4948, 78.3996, ["Busy Hub"]),
            ("Miyapur", 17.4968, 78.3414, ["Terminal Point"]),
            ("Ameerpet", 17.4375, 78.4482, ["Metro Connect"]),
            ("Begumpet", 17.4447, 78.4664, ["Elite Zone"]),
            ("Secunderabad", 17.4399, 78.4983, ["Station Box"]),
            ("Uppal", 17.3984, 78.5583, ["Highway Swap"]),
            ("LB Nagar", 17.3457, 78.5522, ["Ring Road Point"]),
            ("Dilsukhnagar", 17.3688, 78.5247, ["Market Hub"]),
            ("Malakpet", 17.3756, 78.4901, ["Heritage Point"]),
            ("Mehdipatnam", 17.3958, 78.4312, ["Central Junction"]),
            ("Manikonda", 17.3970, 78.3762, ["Rising Tech"]),
            ("Tolichowki", 17.3982, 78.4152, ["Food Plaza"]),
            ("Hafeezpet", 17.4772, 78.3542, ["Suburban Link"]),
            ("Nanakramguda", 17.4172, 78.3442, ["Financial District"]),
        ]

        station_types = ["automated", "manual", "hybrid"]
        power_types = ["grid", "solar", "hybrid"]
        
        for i, (area, lat, lon, ams) in enumerate(areas):
            station = Station(
                name=f"Wezu {area} {'X-Press' if i%3==0 else 'Station'}",
                address=f"Phase {random.randint(1,5)}, {area}, Hyderabad, TS",
                latitude=lat + (random.random() - 0.5) * 0.005,
                longitude=lon + (random.random() - 0.5) * 0.005,
                vendor_id=vendor.id,
                dealer_id=dealer.id if (dealer and i % 4 == 0) else None,
                station_type=random.choice(station_types),
                power_type=random.choice(power_types),
                is_24x7=i % 5 != 0,
                rating=round(4.0 + random.random(), 1),
                total_reviews=random.randint(50, 500),
                status="active" if i % 12 != 0 else "maintenance",
                total_slots=random.choice([12, 18, 24]),
                amenities=",".join(ams),
                contact_phone="+910000000000",
                contact_email=f"station{i}@wezu.com"
            )
            session.add(station)
            session.commit()
            session.refresh(station)

            # Add multiple images for richness
            for k in range(2):
                img = StationImage(
                    station_id=station.id,
                    url=f"https://images.unsplash.com/photo-1611333162391-76bcbf042431?w=800&q=80" if k==0 else "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=800&q=80",
                    is_primary=(k == 0)
                )
                session.add(img)

            # Seed Batteries & Slots
            num_batteries = random.randint(min(5, station.total_slots), station.total_slots - 2)
            for j in range(station.total_slots):
                slot = StationSlot(
                    station_id=station.id,
                    slot_number=j + 1,
                    status="empty"
                )
                
                if j < num_batteries:
                    battery = Battery(
                        serial_number=f"WZ-{area[:3].upper()}-{i:02d}-{j:02d}",
                        battery_type=random.choice(["Li-ion", "LiFePO4"]),
                        capacity_mah=random.choice([20000, 30000, 45000]),
                        voltage_v=random.choice([48.0, 60.0]),
                        manufacturer="Wezu Energy",
                        model_number=f"PRO-{random.randint(100,500)}",
                        status="ready" if station.status == "active" else "charging",
                        current_charge=random.uniform(85.0, 100.0),
                        health_percentage=random.uniform(90.0, 100.0),
                        cycle_count=random.randint(0, 50),
                        location_type="station",
                        location_id=station.id,
                        rental_price_per_day=random.choice([50.0, 75.0, 99.0]),
                        damage_deposit_amount=500.0
                    )
                    session.add(battery)
                    session.commit()
                    session.refresh(battery)
                    
                    slot.battery_id = battery.id
                    slot.status = "ready"
                
                session.add(slot)
            
            session.commit()
        
        print(f"DONE: Seeded 20 unique stations and {len(areas)} areas.")

if __name__ == "__main__":
    from sqlalchemy import text
    seed_stations()
