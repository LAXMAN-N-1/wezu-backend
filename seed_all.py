import sys
import os
import random
import uuid
from datetime import datetime, timedelta

# Add the current directory to the path so we can import app
sys.path.insert(0, os.path.abspath("."))

from app.db.session import get_session, engine
from sqlmodel import SQLModel, select
from app.core.security import get_password_hash
from app.models import (
    User, UserType, UserStatus, 
    Battery, BatteryCatalog, BatteryStatus, 
    Station, StationSlot, StationStatus,
    City, Region, Country, Continent, Zone,
    Rental, RentalStatus, BatteryHealthSnapshot
)

def seed():
    # 1. Create all tables in the default schema (public)
    print("Ensuring all tables exist in the public schema...")
    SQLModel.metadata.create_all(engine)
    
    db = next(get_session())
    
    # 2. Seed Geography
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

    # 3. Seed Users
    print("Seeding Users...")
    admin = db.exec(select(User).where(User.user_type == UserType.ADMIN)).first()
    if not admin:
        admin = User(
            phone_number="9999999999",
            email="admin@wezu.com",
            full_name="System Admin",
            user_type=UserType.ADMIN,
            status=UserStatus.ACTIVE,
            is_superuser=True,
            hashed_password=get_password_hash("Admin@123")
        )
        db.add(admin)
        
    customer = db.exec(select(User).where(User.user_type == UserType.CUSTOMER)).first()
    if not customer:
        customer = User(
            phone_number="8888888888",
            email="customer@wezu.com",
            full_name="Demo Customer",
            user_type=UserType.CUSTOMER,
            status=UserStatus.ACTIVE,
            hashed_password=get_password_hash("password")
        )
        db.add(customer)
    db.commit()
    db.refresh(admin)
    db.refresh(customer)

    # 4. Seed Battery Catalog
    print("Seeding Battery Catalog...")
    cat1 = db.exec(select(BatteryCatalog).where(BatteryCatalog.name == "Standard LFP")).first()
    if not cat1:
        cat1 = BatteryCatalog(
            name="Standard LFP", brand="Exide",
            voltage=48.0, capacity_mah=30000, weight_kg=15.0,
            battery_type="lfp", is_active=True
        )
        db.add(cat1)
    
    cat2 = db.exec(select(BatteryCatalog).where(BatteryCatalog.name == "Performance NMC")).first()
    if not cat2:
        cat2 = BatteryCatalog(
             name="Performance NMC", brand="Panasonic",
            voltage=72.0, capacity_mah=40000, weight_kg=22.0,
            battery_type="nmc", is_active=True
        )
        db.add(cat2)
    db.commit()
    db.refresh(cat1)
    db.refresh(cat2)

    # 5. Seed Stations
    print("Seeding Stations...")
    stations = db.exec(select(Station)).all()
    if len(stations) < 5:
        for i in range(5):
            s = Station(
                name=f"Station Indiranagar {i+1}",
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
            stations.append(s)
        db.commit()
        for s in stations: db.refresh(s)

    # 6. Seed Batteries
    print("Seeding Batteries...")
    batteries = db.exec(select(Battery)).all()
    if len(batteries) < 50:
        needed = 50 - len(batteries)
        for i in range(needed):
            b = Battery(
                serial_number=f"WZ-{uuid.uuid4().hex[:8].upper()}",
                sku_id=random.choice([cat1.id, cat2.id]),
                status=random.choice(list(BatteryStatus)),
                health_percentage=random.uniform(70.0, 100.0),
                current_charge=random.uniform(20.0, 95.0),
                manufacturer="Wezu Energy",
                battery_type=random.choice(["LFP", "NMC"])
            )
            db.add(b)
            batteries.append(b)
        db.commit()
        for b in batteries: db.refresh(b)

    # 7. Seed Station Slots & Place Batteries
    print("Placing Batteries in Stations...")
    for s in stations:
        # Check existing slots
        slots = db.exec(select(StationSlot).where(StationSlot.station_id == s.id)).all()
        if not slots:
            for j in range(s.total_slots):
                slot = StationSlot(
                    station_id=s.id,
                    slot_number=j+1,
                    status="empty"
                )
                db.add(slot)
            db.commit()
            
    # Randomly assign 30 batteries to station slots
    avail_batteries = [b for b in batteries if b.status == BatteryStatus.AVAILABLE]
    avail_slots = db.exec(select(StationSlot).where(StationSlot.status == "empty")).all()
    
    random.shuffle(avail_batteries)
    random.shuffle(avail_slots)
    
    count = min(len(avail_batteries), len(avail_slots), 30)
    for i in range(count):
        b = avail_batteries[i]
        slot = avail_slots[i]
        slot.battery_id = b.id
        slot.status = "charging" if b.current_charge < 90 else "ready"
        b.status = BatteryStatus.CHARGING if slot.status == "charging" else BatteryStatus.AVAILABLE
        b.station_id = slot.station_id
        db.add(slot)
        db.add(b)
    db.commit()

    # 8. Seed Rentals
    print("Seeding Rentals...")
    rented_batteries = [b for b in batteries if b.status == BatteryStatus.RENTED]
    if len(rented_batteries) < 5:
        avail_for_rent = [b for b in batteries if b.status == BatteryStatus.AVAILABLE]
        for i in range(min(len(avail_for_rent), 5)):
            b = avail_for_rent[i]
            b.status = BatteryStatus.RENTED
            b.current_user_id = customer.id
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
            db.add(b)
            db.add(rental)
    db.commit()

    # 9. Seed Health Snapshots
    print("Seeding Battery Health History...")
    for b in batteries:
        # If no snapshots, add history
        exists = db.exec(select(BatteryHealthSnapshot).where(BatteryHealthSnapshot.battery_id == b.id).limit(1)).first()
        if not exists:
            curr_health = b.health_percentage
            for d in range(90, -1, -10):
                snap_health = curr_health + random.uniform(0, 5) if d > 0 else curr_health
                db.add(BatteryHealthSnapshot(
                    battery_id=b.id,
                    health_percentage=min(100.0, snap_health),
                    voltage=48.0 + random.uniform(-1, 2),
                    temperature=25.0 + random.uniform(5, 15),
                    recorded_at=datetime.utcnow() - timedelta(days=d)
                ))
    db.commit()
    
    print("\nSuccessfully seeded all tables!")
    print(f"- 5 Stations in Indiranagar")
    print(f"- 50 Batteries across various statuses")
    print(f"- 1 Admin and 1 Customer")
    print(f"- Active and historical data for analytics")

if __name__ == "__main__":
    seed()
