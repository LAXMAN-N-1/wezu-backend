from __future__ import annotations
import os
import random
from datetime import datetime, timezone
from sqlmodel import Session, create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def seed_stations():
    base_lat = 17.4880031
    base_lon = 78.4150736
    
    with Session(engine) as session:
        count = session.execute(text("SELECT count(*) FROM stations")).one()[0]
        if count >= 50:
            print("Already seeded stations:", count)
            return

        print("Seeding stations via raw SQL with casts...")
        for i in range(50):
            lat = base_lat + random.uniform(-0.05, 0.05)
            lon = base_lon + random.uniform(-0.05, 0.05)
            avail = random.randint(1, 10)
            
            session.execute(text("""
                INSERT INTO stations (
                    name, latitude, longitude, address, status, 
                    total_slots, available_batteries, available_slots, 
                    rating, is_24x7, temperature_control, low_stock_threshold_pct, total_reviews,
                    station_type, tenant_id, approval_status,
                    created_at, updated_at
                ) VALUES (
                    :name, :lat, :lon, :addr, 'OPERATIONAL'::stationstatus,
                    10, :avail, 0,
                    :rating, true, false, 20.0, 0,
                    'automated', 'default', 'approved',
                    :now, :now
                )
            """), {
                "name": f"Wezu Station {i+1}",
                "lat": lat,
                "lon": lon,
                "addr": f"Kukatpally Area {i+1}, Hyderabad",
                "avail": avail,
                "rating": round(random.uniform(3.5, 5.0), 1),
                "now": datetime.now(timezone.utc)
            })
            
        session.execute(text("UPDATE stations SET available_slots = total_slots - available_batteries"))
        session.commit()
        print("Stations seeded successfully.")

if __name__ == "__main__":
    seed_stations()
