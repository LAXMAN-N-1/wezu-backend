import sys
import os
import random
import uuid
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery, BatteryAuditLog, BatteryHealthHistory, BatteryStatus, LocationType

def seed_advanced_batteries():
    with Session(engine) as session:
        print("🚀 Starting Advanced Battery Seeding...")

        # 1. Get references
        admin = session.exec(select(User).where(User.is_superuser == True)).first()
        station = session.exec(select(Station)).first()
        
        if not admin:
            print("❌ No admin user found. Please run seed_rbac.py first.")
            return

        # 2. Cleanup existing batteries to avoid serial conflicts for this test
        # session.execute("TRUNCATE inventory.batteries CASCADE") # Optional: risky in collective dev
        
        manufacturers = ["WEZU Energy", "Exide Powers", "Amara Raja", "Tata AutoComp"]
        battery_types = ["48V/30Ah", "60V/40Ah", "72V/50Ah"]
        statuses = [BatteryStatus.AVAILABLE, BatteryStatus.RENTED, BatteryStatus.MAINTENANCE]
        locations = [LocationType.WAREHOUSE, LocationType.STATION, LocationType.SERVICE_CENTER]

        for i in range(25):
            serial = f"BAT-2024-{100+i:03d}"
            
            # Check if exists
            existing = session.exec(select(Battery).where(Battery.serial_number == serial)).first()
            if existing:
                print(f"⏩ Battery {serial} already exists. Skipping.")
                continue
                
            status = random.choice(statuses)
            loc_type = random.choice(locations)
            
            battery = Battery(
                id=uuid.uuid4(),
                serial_number=serial,
                battery_type=random.choice(battery_types),
                manufacturer=random.choice(manufacturers),
                status=status,
                location_type=loc_type,
                station_id=station.id if loc_type == LocationType.STATION and station else None,
                health_percentage=random.uniform(75, 100),
                total_cycles=random.randint(10, 500),
                current_charge=random.uniform(20, 100),
                manufacture_date=datetime.utcnow() - timedelta(days=random.randint(100, 400)),
                purchase_date=datetime.utcnow() - timedelta(days=random.randint(50, 100)),
                warranty_expiry=datetime.utcnow() + timedelta(days=random.randint(200, 700)),
                created_by=admin.id,
                notes=f"Test battery {i} seeded for advanced UI testing."
            )
            session.add(battery)
            session.flush() # Secure the ID for logs

            # 3. Add History
            # Audit Logs
            for j in range(random.randint(3, 8)):
                audit = BatteryAuditLog(
                    battery_id=battery.id,
                    changed_by=admin.id,
                    field_changed=random.choice(["status", "health_percentage", "location_type"]),
                    old_value="Initial",
                    new_value="Updated",
                    reason="Automated Lifecycle Sync",
                    timestamp=datetime.utcnow() - timedelta(days=j*10)
                )
                session.add(audit)

            # Health History
            for k in range(10):
                hist = BatteryHealthHistory(
                    battery_id=battery.id,
                    health_percentage=100 - (k * random.uniform(0.1, 0.5)),
                    recorded_at=datetime.utcnow() - timedelta(days=(10-k)*7)
                )
                session.add(hist)

            print(f"✅ Seeded {serial} with history.")

        session.commit()
        print("✨ Advanced Battery Seeding Complete!")

if __name__ == "__main__":
    seed_advanced_batteries()
