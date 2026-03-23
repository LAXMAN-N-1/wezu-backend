import sys
import os
import random
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath("."))
from app.db.session import get_session
from sqlmodel import select
from app.models.battery_catalog import BatteryCatalog
from app.models.battery import Battery, BatteryHealth, LocationType, BatteryStatus
from app.models.battery_health import BatteryHealthSnapshot

def generate_catalog_id(db):
    print("Checking catalog...")
    cat = db.exec(select(BatteryCatalog).limit(1)).first()
    if cat: return cat.id
    
    cats = [
        BatteryCatalog(
            name="Standard LFP", brand="Exide",
            voltage=48.0, capacity_mah=30000, weight_kg=15.0,
            battery_type="lfp", is_active=True
        ),
        BatteryCatalog(
             name="Performance NMC", brand="Panasonic",
            voltage=72.0, capacity_mah=40000, weight_kg=22.0,
            battery_type="nmc", is_active=True
        )
    ]
    db.add_all(cats)
    db.commit()
    return cats[0].id

def seed():
    db = next(get_session())
    cat_id = generate_catalog_id(db)
    
    print("Checking batteries...")
    existing_bats = db.exec(select(Battery)).all()
    needed = max(0, 50 - len(existing_bats))
    
    if needed > 0:
        print(f"Creating {needed} more batteries...")
        new_bats = []
        for i in range(needed):
            b = Battery(
                serial_number=f"DEMO-{uuid.uuid4().hex[:6].upper()}",
                sku_id=cat_id,
                status=random.choice(list(BatteryStatus)),
                health_percentage=random.uniform(35.0, 100.0),
                location_type=random.choice(list(LocationType)),    
                manufacturer="Demo Corp",
                battery_type="LFP"
            )
            b.current_charge = random.uniform(20.0, b.health_percentage)
            db.add(b)
            new_bats.append(b)
        db.commit()
        for b in new_bats: db.refresh(b)
        existing_bats.extend(new_bats)

    print("Ensuring catalog specs and historical data for all batteries...")
    for b in existing_bats:
        if b.sku_id is None:
            b.sku_id = cat_id
            db.add(b)
        
        # Check if it already has snapshots
        snap_count = len(db.exec(select(BatteryHealthSnapshot).where(BatteryHealthSnapshot.battery_id == b.id)).all())
        if snap_count == 0:
            health = b.health_percentage + random.uniform(5.0, 15.0)
            for d in range(90, -1, -5):
                db.add(BatteryHealthSnapshot(
                    battery_id=b.id,
                    health_percentage=min(100.0, max(0.0, health)),
                    voltage=48.0 + random.uniform(-1, 0.5),
                    temperature=30.0 + random.uniform(-5, 15),
                    recorded_at=datetime.utcnow() - timedelta(days=d)
                ))
                health -= random.uniform(0.1, 0.5)
    
    db.commit()
    print("Data seeded!")

if __name__ == "__main__":
    seed()
