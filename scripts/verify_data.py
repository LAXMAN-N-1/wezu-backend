import os, sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select, func
from app.db.session import engine
import app.models.all
from app.models.battery import Battery, BatteryStatus
from app.models.station import Station
from app.models.dealer import DealerProfile
from app.models.user import User

with Session(engine) as db:
    # Find Laxman
    user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == user.id)).first()
    print(f"Dealer: {dealer.business_name} (id={dealer.id}, user_id={dealer.user_id})")
    
    # Find stations
    stations = db.exec(select(Station).where(Station.dealer_id == dealer.id)).all()
    print(f"\nStations for dealer_id={dealer.id}: {len(stations)}")
    
    for s in stations:
        total = db.exec(select(func.count(Battery.id)).where(Battery.station_id == s.id)).one()
        avail = db.exec(select(func.count(Battery.id)).where(Battery.station_id == s.id, Battery.status == BatteryStatus.AVAILABLE)).one()
        rented = db.exec(select(func.count(Battery.id)).where(Battery.station_id == s.id, Battery.status == BatteryStatus.RENTED)).one()
        maint = db.exec(select(func.count(Battery.id)).where(Battery.station_id == s.id, Battery.status == BatteryStatus.MAINTENANCE)).one()
        retired = db.exec(select(func.count(Battery.id)).where(Battery.station_id == s.id, Battery.status == BatteryStatus.RETIRED)).one()
        
        print(f"\n  Station: {s.name} (id={s.id})")
        print(f"    Total: {total}")
        print(f"    Available: {avail}")
        print(f"    Rented: {rented}")
        print(f"    Maintenance: {maint}")
        print(f"    Retired/Damaged: {retired}")
        print(f"    station.available_batteries (stored): {s.available_batteries}")
    
    # Warehouse
    wh = db.exec(select(func.count(Battery.id)).where(Battery.station_id == None, Battery.notes == "seed_laxman_script")).one()
    print(f"\n  Warehouse batteries: {wh}")
    
    # Total
    total_all = db.exec(select(func.count(Battery.id)).where(Battery.notes == "seed_laxman_script")).one()
    print(f"\n  TOTAL seeded batteries: {total_all}")
