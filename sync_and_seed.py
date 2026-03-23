import sys
import os
import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text, inspect

# Disable background tasks during seeding
os.environ["ENABLE_SCHEDULER"] = "false"

# Add the current directory to the path so we can import app
sys.path.insert(0, os.path.abspath("."))

from app.db.session import get_session, engine
from sqlmodel import SQLModel, select, Session
from app.models import (
    User, UserType, UserStatus, 
    Battery, BatteryCatalog, BatteryStatus, 
    Station, StationSlot, StationStatus,
    City, Region, Country, Continent, Zone,
    Rental, RentalStatus, BatteryHealthSnapshot,
    BatteryAuditLog, BatteryLifecycleEvent
)

def sync_schema():
    print("Synchronizing Schema (Adding missing columns)...")
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        for table_name, table in SQLModel.metadata.tables.items():
            clean_table_name = table_name.split('.')[-1]
            
            if not inspector.has_table(clean_table_name):
                print(f"Table {clean_table_name} missing. Creating...")
                table.create(engine)
                continue
            
            existing_columns = [c['name'] for c in inspector.get_columns(clean_table_name)]
            for column in table.columns:
                if column.name not in existing_columns:
                    print(f"Adding missing column {column.name} to {clean_table_name}...")
                    type_str = str(column.type.compile(engine.dialect))
                    sql = f"ALTER TABLE {clean_table_name} ADD COLUMN {column.name} {type_str}"
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                    except Exception as e:
                        print(f"Error adding {column.name} to {clean_table_name}: {e}")
                        conn.rollback()

def seed():
    sync_schema()
    
    db = next(get_session())
    
    print("\nStarting Seeding Process...")
    
    # 2. Seed Geography
    try:
        print("Seeding Geography...")
        continent = db.exec(select(Continent).where(Continent.name == "Asia")).first()
        if not continent:
            continent = Continent(name="Asia")
            db.add(continent)
            db.commit()
            db.refresh(continent)
        
        country = db.exec(select(Country).where(Country.name == "India")).first()
        if not country:
            country = Country(name="India", continent_id=continent.id)
            db.add(country)
            db.commit()
            db.refresh(country)
            
        region = db.exec(select(Region).where(Region.name == "Karnataka")).first()
        if not region:
            region = Region(name="Karnataka", country_id=country.id)
            db.add(region)
            db.commit()
            db.refresh(region)
            
        city = db.exec(select(City).where(City.name == "Bengaluru")).first()
        if not city:
            city = City(name="Bengaluru", region_id=region.id)
            db.add(city)
            db.commit()
            db.refresh(city)
            
        zone = db.exec(select(Zone).where(Zone.name == "Indiranagar")).first()
        if not zone:
            zone = Zone(name="Indiranagar", city_id=city.id)
            db.add(zone)
            db.commit()
            db.refresh(zone)
        print("Geography seeded.")
    except Exception as e:
        print(f"Geography error: {e}")
        db.rollback()

    # 3. Seed Users
    try:
        print("Seeding Users...")
        admin = db.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not admin:
            admin = User(
                phone_number="9999999999",
                email="admin@wezu.com",
                full_name="System Admin",
                user_type=UserType.ADMIN,
                status=UserStatus.ACTIVE,
                is_superuser=True
            )
            db.add(admin)
            
        customer = db.exec(select(User).where(User.email == "customer@wezu.com")).first()
        if not customer:
            customer = User(
                phone_number="8888888888",
                email="customer@wezu.com",
                full_name="Demo Customer",
                user_type=UserType.CUSTOMER,
                status=UserStatus.ACTIVE
            )
            db.add(customer)
        db.commit()
        db.refresh(admin)
        db.refresh(customer)
        print("Users seeded.")
    except Exception as e:
        print(f"Users error: {e}")
        db.rollback()

    # 4. Seed Battery Catalog
    try:
        print("Seeding Battery Catalog...")
        cat = db.exec(select(BatteryCatalog).limit(1)).first()
        if not cat:
            cat = BatteryCatalog(
                name="Standard LFP", brand="Exide",
                voltage=48.0, capacity_mah=30000, weight_kg=15.0,
                battery_type="lfp", is_active=True
            )
            db.add(cat)
            db.commit()
            db.refresh(cat)
        print("Catalog seeded.")
    except Exception as e:
        print(f"Catalog error: {e}")
        db.rollback()

    # 5. Seed Stations
    try:
        print("Seeding Stations...")
        stations = list(db.exec(select(Station)).all())
        if len(stations) < 5:
            for i in range(5 - len(stations)):
                s = Station(
                    name=f"Station Indiranagar {len(stations)+i+1}",
                    address=f"Indiranagar 100ft Rd, Block {i+1}",
                    latitude=12.9716 + random.uniform(-0.01, 0.01),
                    longitude=77.6412 + random.uniform(-0.01, 0.01),
                    zone_id=zone.id,
                    owner_id=admin.id,
                    total_slots=12,
                    available_slots=12,
                    available_batteries=0,
                    status=StationStatus.OPERATIONAL
                )
                db.add(s)
            db.commit()
            stations = list(db.exec(select(Station)).all())
        print(f"Stations count: {len(stations)}")
    except Exception as e:
        print(f"Stations error: {e}")
        db.rollback()

    # 6. Seed Batteries
    try:
        print("Seeding Batteries...")
        batteries = list(db.exec(select(Battery)).all())
        if len(batteries) < 50:
            for i in range(50 - len(batteries)):
                b = Battery(
                    serial_number=f"WZ-{uuid.uuid4().hex[:8].upper()}",
                    sku_id=cat.id,
                    status=BatteryStatus.AVAILABLE,
                    health_percentage=random.uniform(70.0, 100.0),
                    current_charge=random.uniform(20.0, 95.0),
                    manufacturer="Wezu Energy",
                    battery_type="lfp"
                )
                db.add(b)
            db.commit()
            batteries = list(db.exec(select(Battery)).all())
        print(f"Batteries count: {len(batteries)}")
    except Exception as e:
        print(f"Batteries error: {e}")
        db.rollback()

    # 7. Seed Station Slots
    try:
        print("Seeding Slots...")
        for s in stations:
            slots_count = db.exec(text(f"SELECT count(*) FROM station_slots WHERE station_id = {s.id}")).first()[0]
            if slots_count == 0:
                for j in range(s.total_slots):
                    db.add(StationSlot(station_id=s.id, slot_number=j+1, status="empty"))
        db.commit()
        print("Slots seeded.")
    except Exception as e:
        print(f"Slots error: {e}")
        db.rollback()

    # 8. Seed Rentals
    try:
        print("Seeding Rentals...")
        rentals_count = db.exec(select(text("count(*) FROM rentals"))).first()[0]
        if rentals_count == 0:
            for i in range(min(len(batteries), 10)):
                b = batteries[i]
                rental = Rental(
                    user_id=customer.id,
                    battery_id=b.id,
                    start_station_id=random.choice(stations).id,
                    start_time=datetime.utcnow() - timedelta(hours=random.randint(1, 24)),
                    expected_end_time=datetime.utcnow() + timedelta(hours=12),
                    status=RentalStatus.ACTIVE,
                    start_battery_level=b.current_charge + random.uniform(5, 10),
                    currency="INR"
                )
                db.add(rental)
            db.commit()
        print(f"Rentals count: {db.exec(select(text('count(*) FROM rentals'))).first()[0]}")
    except Exception as e:
        print(f"Rentals error: {e}")
        db.rollback()

    # 9. Seed Health History
    try:
        print("Seeding Health Snapshots...")
        snapshots_count = db.exec(select(text("count(*) FROM battery_health_snapshots"))).first()[0]
        if snapshots_count < 100:
            for b in batteries[:10]:
                for d in range(10):
                    db.add(BatteryHealthSnapshot(
                        battery_id=b.id,
                        health_percentage=b.health_percentage - random.uniform(0, 1),
                        recorded_at=datetime.utcnow() - timedelta(days=d)
                    ))
            db.commit()
        print("Health snapshots seeded.")
    except Exception as e:
        print(f"Health error: {e}")
        db.rollback()

    print("\nFinalizing Seeding...")
    print("Done!")

if __name__ == "__main__":
    seed()
