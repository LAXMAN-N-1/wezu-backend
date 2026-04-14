import os
import sys
import random
from datetime import datetime, UTC

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select, func
from app.db.session import engine
import app.models.all
from app.models.user import User, UserType, UserStatus
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.battery import Battery, BatteryStatus, BatteryHealth, LocationType
from app.core.security import get_password_hash
import uuid

NOW = datetime.now(UTC)

def fully_dynamic_seed():
    with Session(engine) as db:
        print("Starting Fully Dynamic Seed for Wezu...")

        # 1. Look up Wezu Dealer dynamically by email
        dealer_user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if not dealer_user:
            dealer_user = User(
                email="dealer@wezu.com",
                phone_number="8888888888",
                full_name="Wezu Dealer Kumar",
                hashed_password=get_password_hash("wezu123"),
                user_type=UserType.DEALER,
                status=UserStatus.ACTIVE,
            )
            db.add(dealer_user)
            db.commit()
            db.refresh(dealer_user)
        else:
            # Ensure password is updated to new requirement
            dealer_user.hashed_password = get_password_hash("wezu123")
            db.add(dealer_user)
            db.commit()
            db.refresh(dealer_user)
            
        # 2. Look up his correct dealer profile ID
        dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == dealer_user.id)).first()
        if not dealer:
            print("Dealer profile missing for Wezu Dealer. Creating one.")
            dealer = DealerProfile(
                user_id=dealer_user.id,
                business_name="Wezu Energy Solutions",
                contact_email="dealer@wezu.com",
                contact_phone="8888888888",
                status="approved"
            )
            db.add(dealer)
            db.commit()
            db.refresh(dealer)

        # 3. Unlink any old/stale stations from this dealer (keep only the 2 we want)
        wezu_station_names = ["kakinda station", "golapudi sttaion"]
        old_stations = db.exec(
            select(Station).where(
                Station.dealer_id == dealer.id,
                Station.name.notin_(wezu_station_names)
            )
        ).all()
        for old_st in old_stations:
            old_st.dealer_id = None
            db.add(old_st)
        if old_stations:
            db.commit()
            print(f"Unlinked {len(old_stations)} stale stations from Wezu Dealer")

        # 4. Create or update stations with EXACT correct dealer_id
        stations_data = {
            "kakinda station": {"total": 100, "lat": 16.9891, "lng": 82.2475, "city": "Kakinada"},
            "golapudi sttaion": {"total": 120, "lat": 16.5366, "lng": 80.5960, "city": "Vijayawada"}
        }
        
        stations = {}
        for s_name, data in stations_data.items():
            st = db.exec(select(Station).where(Station.name == s_name)).first()
            if not st:
                st = Station(
                    name=s_name,
                    address=f"Main Road, {data['city']}",
                    city=data['city'],
                    latitude=data['lat'],
                    longitude=data['lng'],
                    station_type="automated",
                    total_slots=data['total'],
                    status="OPERATIONAL",
                    is_24x7=True,
                    dealer_id=dealer.id, # Dynamically assigned!
                    available_batteries=0,
                    available_slots=data['total'],
                )
                db.add(st)
                db.commit()
                db.refresh(st)
            else:
                # Update it if it was created by a previous bad run
                st.dealer_id = dealer.id 
                db.add(st)
                db.commit()
            
            # Ensure slots exist so batteries can be housed structurally
            existing_slots = db.exec(select(StationSlot).where(StationSlot.station_id == st.id)).all()
            if len(existing_slots) < st.total_slots:
                for i in range(len(existing_slots), st.total_slots):
                    db.add(StationSlot(
                        station_id=st.id,
                        slot_number=i+1,
                        status="empty",
                        is_locked=True
                    ))
                db.commit()
                
            stations[s_name] = st

        kakinada_id = stations["kakinda station"].id
        gollapudi_id = stations["golapudi sttaion"].id

        # 4. Idempotency: Purge old dynamically assigned seed batteries
        print("Purging old seed records safely...")
        from sqlalchemy import text
        db.exec(text(f"UPDATE core.station_slots SET battery_id = NULL, status = 'empty' WHERE station_id IN ({kakinada_id}, {gollapudi_id})"))
        db.exec(text("DELETE FROM core.batteries WHERE notes = 'seed_wezu_script'"))
        db.commit()

        # 5. Exact Distribution of 1000 Total Batteries
        config_kakinda = {
            BatteryStatus.AVAILABLE: 60,
            BatteryStatus.RENTED: 20,
            BatteryStatus.MAINTENANCE: 10,
            BatteryStatus.RETIRED: 10 # Represents damaged
        }
        
        config_golapudi = {
            BatteryStatus.AVAILABLE: 80,
            BatteryStatus.RENTED: 20,
            BatteryStatus.MAINTENANCE: 10,
            BatteryStatus.RETIRED: 10
        }
        
        def create_bats(count, st_id, status_distribution):
            bats = []
            distribution = []
            for status, amount in status_distribution.items():
                distribution.extend([status] * amount)
            
            for i in range(count):
                status = distribution[i] if i < len(distribution) else BatteryStatus.AVAILABLE
                health = BatteryHealth.GOOD
                if status == BatteryStatus.MAINTENANCE:
                    health = BatteryHealth.FAIR
                elif status == BatteryStatus.RETIRED:
                    health = BatteryHealth.DAMAGED
                
                bat = Battery(
                    serial_number=f"WEZU-BATT-{st_id if st_id else 'ADM'}-{uuid.uuid4().hex[:8]}",
                    qr_code_data=f"QR-WEZU-{uuid.uuid4().hex[:12]}",
                    station_id=st_id,
                    status=status,
                    health_status=health,
                    current_charge=random.uniform(20, 100) if status != BatteryStatus.RETIRED else 0.0,
                    location_type=LocationType.STATION if st_id else LocationType.WAREHOUSE,
                    notes="seed_wezu_script"
                )
                bats.append(bat)
            return bats

        all_new_bats = []
        kak_bats = create_bats(100, kakinada_id, config_kakinda)
        gol_bats = create_bats(120, gollapudi_id, config_golapudi)
        wh_bats = create_bats(780, None, {BatteryStatus.AVAILABLE: 780})
        
        all_new_bats.extend(kak_bats)
        all_new_bats.extend(gol_bats)
        all_new_bats.extend(wh_bats)
        
        db.add_all(all_new_bats)
        db.commit()

        # Re-fetch batteries to get their generated IDs
        saved_kak = db.exec(select(Battery).where(Battery.station_id == kakinada_id, Battery.notes == "seed_wezu_script")).all()
        saved_gol = db.exec(select(Battery).where(Battery.station_id == gollapudi_id, Battery.notes == "seed_wezu_script")).all()
        
        # 6. Assign batteries physically to their station slots
        def assign_to_slots(station_id, station_bats):
            st_slots = db.exec(select(StationSlot).where(StationSlot.station_id == station_id)).all()
            for idx, bat in enumerate(station_bats):
                if idx < len(st_slots):
                    st_slots[idx].battery_id = bat.id
                    st_slots[idx].status = "charging" if bat.status == BatteryStatus.AVAILABLE else "error"
                    db.add(st_slots[idx])

        assign_to_slots(kakinada_id, saved_kak)
        assign_to_slots(gollapudi_id, saved_gol)
        db.commit()
        
        # Update station fast-counts
        for s_name, st in stations.items():
            avail_count = db.exec(select(func.count(Battery.id)).where(
                Battery.station_id == st.id, Battery.status == BatteryStatus.AVAILABLE
            )).one() or 0
            
            total_bats = db.exec(select(func.count(Battery.id)).where(Battery.station_id == st.id)).one() or 0
            
            st.available_batteries = avail_count
            st.available_slots = max(0, st.total_slots - total_bats)
            db.add(st)
        
        db.commit()
        print(f"✅ Success! Generated 1000 dynamically mapped batteries.")

if __name__ == '__main__':
    fully_dynamic_seed()
