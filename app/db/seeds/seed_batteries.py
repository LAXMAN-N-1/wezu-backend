import os
import sys
import uuid
import random
from datetime import datetime, UTC, timedelta

# We are in backend
sys.path.insert(0, os.path.abspath("."))

from app.db.session import get_session
from app.models.battery import Battery, BatteryStatus, BatteryHealth, LocationType
from sqlmodel import select

def seed_batteries():
    db = next(get_session())
    print("Checking existing batteries...")
    existing = len(db.exec(select(Battery)).all())
    if existing > 0:
        print(f"Adding 50 batteries to the existing {existing} batteries...")
    else:
        print("No batteries found, seeding 50 batteries...")
    
    manufacturers = ["Exide", "Luminous", "Amaron", "Tesla", "Panasonic"]
    battery_types = ["Li-ion", "Lead-Acid", "LiFePO4"]
    statuses = list(BatteryStatus)
    healths = list(BatteryHealth)
    locations = list(LocationType)
    
    new_batteries = []
    for i in range(50):
        # Using a deterministic but unique sequence for testing
        now = datetime.now(UTC)
        b = Battery(
            serial_number=f"BAT-{uuid.uuid4().hex[:8].upper()}",
            qr_code_data=f"QR-{uuid.uuid4().hex[:12].upper()}",
            status=random.choice(statuses),
            health_status=random.choice([BatteryHealth.GOOD, BatteryHealth.GOOD, BatteryHealth.FAIR, BatteryHealth.POOR]),
            current_charge=random.uniform(10.0, 100.0),
            health_percentage=random.uniform(40.0, 100.0),
            cycle_count=random.randint(0, 500),
            total_cycles=1000,
            temperature_c=random.uniform(20.0, 45.0),
            manufacturer=random.choice(manufacturers),
            battery_type=random.choice(battery_types),
            location_type=random.choice(locations),
            last_maintenance_cycles=random.randint(0, 100),
            state_of_health=random.uniform(50.0, 100.0),
            charge_cycles=random.randint(0, 500)
        )
        # Randomly assign battery to a station (say IDs 1-10) or warehouse
        if b.location_type == LocationType.STATION:
            b.station_id = random.randint(1, 4) # Assuming some stations exist, will leave None if error
            
        new_batteries.append(b)
        db.add(b)
    
    try:
        db.commit()
        print("Successfully seeded 50 batteries.")
    except Exception as e:
        db.rollback()
        print(f"Failed to seed batteries: {e}")
        # Let's try to add without station_id if it failed due to foreign key
        print("Retrying without station IDs...")
        for b in new_batteries:
            b.station_id = None
            db.add(b)
        db.commit()
        print("Successfully seeded 50 batteries without station IDs.")

if __name__ == "__main__":
    seed_batteries()
