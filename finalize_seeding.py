import sys
import os
import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text

# Disable background tasks
os.environ["ENABLE_SCHEDULER"] = "false"

# Add path
sys.path.insert(0, os.path.abspath("."))

from app.db.session import get_session, engine
from sqlmodel import SQLModel, select
from app.models import (
    User, UserType, UserStatus, 
    Battery, BatteryStatus, 
    Station, StationSlot,
    Rental, RentalStatus, BatteryHealthSnapshot,
    BatteryAuditLog, BatteryLifecycleEvent
)

def seed():
    db = next(get_session())
    print("\nStarting Final Seeding...")
    
    # 1. Get Users
    admin = db.exec(select(User).where(User.user_type == UserType.ADMIN)).first()
    customer = db.exec(select(User).where(User.user_type == UserType.CUSTOMER)).first()
    
    if not admin or not customer:
        print("Required users not found. Please run sync_and_seed.py first for core data.")
        return

    # 2. Get Batteries and Stations
    batteries = list(db.exec(select(Battery)).all())
    stations = list(db.exec(select(Station)).all())
    
    if not batteries or not stations:
        print("Required batteries or stations not found.")
        return

    print(f"Using Admin ID: {admin.id}, Customer ID: {customer.id}")
    print(f"Found {len(batteries)} batteries and {len(stations)} stations.")

    # 3. Seed Rentals (if 0)
    try:
        rentals_count = db.exec(text("SELECT count(*) FROM rentals")).first()[0]
        if rentals_count == 0:
            print("Seeding Rentals...")
            for i in range(10):
                b = random.choice(batteries)
                rental = Rental(
                    user_id=customer.id,
                    battery_id=b.id,
                    start_station_id=random.choice(stations).id,
                    start_time=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                    expected_end_time=datetime.utcnow() + timedelta(hours=12),
                    status=RentalStatus.ACTIVE,
                    start_battery_level=random.uniform(80, 100),
                    currency="INR"
                )
                db.add(rental)
            db.commit()
            print(f"Seeded {i+1} rentals.")
        else:
            print(f"Rentals already exist ({rentals_count}).")
    except Exception as e:
        print(f"Rentals error: {e}")
        db.rollback()

    # 4. Seed Audit Logs (if 0)
    try:
        audit_count = db.exec(text("SELECT count(*) FROM battery_audit_logs")).first()[0]
        if audit_count == 0:
            print("Seeding Audit Logs...")
            for i in range(20):
                b = random.choice(batteries)
                db.add(BatteryAuditLog(
                    battery_id=b.id,
                    changed_by=admin.id,
                    field_changed=random.choice(["status", "health_percentage", "current_charge"]),
                    old_value="90",
                    new_value=str(round(random.uniform(70, 95), 2)),
                    reason="Routine inspection",
                    timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                ))
            db.commit()
            print("Seeded 20 audit logs.")
    except Exception as e:
        print(f"Audit error: {e}")
        db.rollback()

    # 5. Seed Lifecycle Events (if 0)
    try:
        lifecycle_count = db.exec(text("SELECT count(*) FROM battery_lifecycle_events")).first()[0]
        if lifecycle_count == 0:
            print("Seeding Lifecycle Events...")
            for i in range(20):
                b = random.choice(batteries)
                db.add(BatteryLifecycleEvent(
                    battery_id=b.id,
                    event_type=random.choice(["commissioned", "deployed", "maintenance", "recharged"]),
                    description=f"Standard activity",
                    location_id=str(random.choice(stations).id),
                    location_type="station",
                    recorded_at=datetime.utcnow() - timedelta(days=random.randint(1, 60))
                ))
            db.commit()
            print("Seeded 20 lifecycle events.")
    except Exception as e:
        print(f"Lifecycle error: {e}")
        db.rollback()

    # 6. Seed Slots if empty
    try:
        for s in stations:
            slots_count = db.exec(text(f"SELECT count(*) FROM station_slots WHERE station_id = {s.id}")).first()[0]
            if slots_count == 0:
                print(f"Seeding slots for station {s.id}...")
                for j in range(s.total_slots):
                    db.add(StationSlot(station_id=s.id, slot_number=j+1, status="empty"))
        db.commit()
    except Exception as e:
        print(f"Slots error: {e}")
        db.rollback()

    print("\nFinal Seeding Complete!")

if __name__ == "__main__":
    seed()
