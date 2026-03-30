import os
import sys
import random
from datetime import datetime, UTC, timedelta
import uuid

# Add the parent directory to sys.path to allow importing from app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from app.db.session import engine
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile
from app.models.station import Station, StationStatus, StationSlot
from app.models.battery import (
    Battery, BatteryStatus, BatteryHealth, LocationType, 
    BatteryLifecycleEvent, BatteryAuditLog, BatteryHealthHistory
)
from app.models.station_stock import StationStockConfig
from app.models.dealer_inventory import DealerInventory, InventoryTransaction
from app.models.rental import Rental, RentalStatus
from app.models.swap import SwapSession
from app.models.financial import Transaction, TransactionStatus, Wallet
from app.models.settlement import Settlement
from app.models.invoice import Invoice
from app.models.refund import Refund
from app.models.maintenance import MaintenanceRecord
from app.core.security import get_password_hash

def seed_data():
    with Session(engine) as session:
        print("Starting Data Seed...")

        # 1. Base Setup (Admin/Dealer/Customer)
        admin = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not admin:
             print("Admin not found. Please run setup_clean_production.py first.")
             return
        
        # 2. Seed Users
        print("Seeding Users...")
        new_users = []
        for i in range(10):
            email = f"customer_{i}@wezutest.com"
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                user = User(
                    email=email,
                    phone_number=f"9000000{i:03d}",
                    full_name=f"Test Customer {i}",
                    hashed_password=get_password_hash("password123"),
                    user_type=UserType.CUSTOMER,
                    status=UserStatus.ACTIVE
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Add wallet
                wallet = Wallet(user_id=user.id, balance=random.uniform(500, 2000))
                session.add(wallet)
                session.commit()
            new_users.append(user)
            
        # 3. Seed Extra Dealers
        print("Seeding Dealers...")
        dealers = session.exec(select(DealerProfile)).all()
        dealer_ids = [d.id for d in dealers]
        for i in range(2):
             if len(dealer_ids) < 3 + i:
                 u_email = f"dealer_extra_{i}@wezutest.com"
                 user = session.exec(select(User).where(User.email == u_email)).first()
                 if not user:
                     user = User(
                        email=u_email,
                        phone_number=f"8000000{i:03d}",
                        full_name=f"Extra Dealer {i}",
                        hashed_password=get_password_hash("password123"),
                        user_type=UserType.DEALER,
                        status=UserStatus.ACTIVE
                     )
                     session.add(user)
                     session.commit()
                     session.refresh(user)
                     
                     dealer = DealerProfile(
                        user_id=user.id,
                        business_name=f"Power Hub {i}",
                        contact_person=f"Dealer Person {i}",
                        contact_email=u_email,
                        contact_phone=f"8000000{i:03d}",
                        address_line1=f"Road {i}",
                        city=["Mumbai", "Delhi", "Bangalore"][i % 3],
                        state="State",
                        pincode="100000",
                        is_active=True
                     )
                     session.add(dealer)
                     session.commit()
                     session.refresh(dealer)
                     dealer_ids.append(dealer.id)
                     dealers.append(dealer)

        # 4. Seed Stations
        print("Seeding Stations...")
        stations = session.exec(select(Station)).all()
        station_names = [s.name for s in stations]
        new_station_names = ["Mumbai Central Station", "Bandra Power", "Delhi Connaught", "Bangalore Tech Park"]
        for name in new_station_names:
             if name not in station_names:
                 lat = round(random.uniform(18.0, 20.0), 6)
                 lng = round(random.uniform(72.0, 74.0), 6)
                 st = Station(
                    name=name,
                    address=f"{name} Rd",
                    city=name.split()[0],
                    latitude=lat,
                    longitude=lng,
                    station_type="automated",
                    total_slots=random.choice([10, 15, 20]),
                    status=StationStatus.OPERATIONAL,
                    is_24x7=True,
                    rating=random.uniform(4.0, 5.0)
                 )
                 session.add(st)
                 session.commit()
                 session.refresh(st)
                 stations.append(st)
                 
                 # Slots
                 for slot_i in range(st.total_slots):
                      slot = StationSlot(
                          station_id=st.id,
                          slot_number=slot_i + 1,
                          status="empty",
                          is_locked=True
                      )
                      session.add(slot)
                 
                 # Station Config
                 config = StationStockConfig(
                     station_id=st.id,
                     max_capacity=st.total_slots * 2,
                     reorder_point=5,
                     reorder_quantity=10
                 )
                 session.add(config)
                 session.commit()

        # 5. Seed Batteries
        print("Seeding Batteries...")
        existing_bats = session.exec(select(Battery)).all()
        target_bats = 50
        batteries = existing_bats.copy()
        
        while len(batteries) < target_bats:
             idx = len(batteries) + 1
             serial = f"WZU-BAT-{idx:04d}"
             
             # Randomize battery state
             status = random.choice(list(BatteryStatus))
             health = random.choice(list(BatteryHealth))
             location = random.choice(list(LocationType))
             station_id = random.choice(stations).id if location == LocationType.STATION else None
             
             bat = Battery(
                 serial_number=serial,
                 status=status,
                 health_status=health,
                 location_type=location,
                 station_id=station_id,
                 current_charge=random.uniform(10.0, 100.0),
                 health_percentage=random.uniform(70.0, 100.0),
                 cycle_count=random.randint(0, 500),
                 total_cycles=5000,
                 battery_type="48V/30Ah",
                 created_by=admin.id
             )
             session.add(bat)
             session.commit()
             session.refresh(bat)
             batteries.append(bat)
             
             # Lifecycle
             le = BatteryLifecycleEvent(
                 battery_id=bat.id,
                 event_type="created",
                 description="Initial provision",
                 actor_id=admin.id
             )
             session.add(le)
             
             # Health History (Past 90 days)
             h = bat.health_percentage
             for d in range(90, 0, -10):
                 hh = BatteryHealthHistory(
                     battery_id=bat.id,
                     health_percentage=min(100.0, h + (d*0.05)),
                     recorded_at=datetime.now(UTC) - timedelta(days=d)
                 )
                 session.add(hh)
             session.commit()

        # 6. Seed Rentals
        print("Seeding Rentals...")
        rentals_added = 0
        for i in range(30):
             user = random.choice(new_users)
             bat = random.choice(batteries)
             start_st = random.choice(stations)
             
             is_active = random.choice([True, False])
             start_time = datetime.now(UTC) - timedelta(days=random.randint(1, 10))
             
             r = Rental(
                 user_id=user.id,
                 battery_id=bat.id,
                 start_station_id=start_st.id,
                 start_time=start_time,
                 expected_end_time=start_time + timedelta(hours=24),
                 status=RentalStatus.ACTIVE if is_active else RentalStatus.COMPLETED,
                 total_amount=random.uniform(100, 500)
             )
             if not is_active:
                 r.end_time = r.start_time + timedelta(hours=random.randint(2, 24))
                 r.end_station_id = random.choice(stations).id
                 r.distance_traveled_km = random.uniform(10, 100)
             
             session.add(r)
             session.commit()
             session.refresh(r)
             rentals_added += 1

        # 7. Seed Transactions & Invoices
        print("Seeding Transactions & Invoices...")
        for i in range(40):
             user = random.choice(new_users)
             amount = random.uniform(50, 1000)
             t = Transaction(
                 user_id=user.id,
                 transaction_type=random.choice(["RENTAL_PAYMENT", "WALLET_TOPUP"]),
                 amount=amount,
                 status=TransactionStatus.SUCCESS,
                 reference_id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
                 created_at=datetime.now(UTC) - timedelta(days=random.randint(0, 30))
             )
             session.add(t)
             session.commit()
             session.refresh(t)
             
             # Create Invoice
             inv = Invoice(
                 user_id=user.id,
                 transaction_id=t.id,
                 invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
                 amount=amount,
                 total=amount,
                 subtotal=amount * 0.82,
                 tax_amount=amount * 0.18,
                 created_at=t.created_at
             )
             session.add(inv)
             
             if random.random() < 0.1: # 10% get refunded
                 ref = Refund(
                     transaction_id=t.id,
                     amount=amount,
                     reason="Customer request",
                     status="processed"
                 )
                 session.add(ref)
        session.commit()

        # 8. Seed Settlements (Dealer Payouts)
        print("Seeding Settlements...")
        for dealer in dealers:
             for m in range(1, 4): # Last 3 months
                 start_date = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0) - timedelta(days=m*30)
                 end_date = start_date + timedelta(days=28)
                 month_str = start_date.strftime("%Y-%m")
                 
                 existing = session.exec(select(Settlement).where(
                     Settlement.dealer_id == dealer.id,
                     Settlement.settlement_month == month_str
                 )).first()
                 
                 if not existing:
                     total_rev = random.uniform(10000, 50000)
                     s = Settlement(
                         dealer_id=dealer.id,
                         settlement_month=month_str,
                         start_date=start_date,
                         end_date=end_date,
                         total_revenue=total_rev,
                         total_commission=total_rev * 0.1,
                         platform_fee=total_rev * 0.05,
                         net_payable=total_rev * 0.05,
                         status=random.choice(["paid", "processing"])
                     )
                     session.add(s)
        session.commit()
        
        # 9. Maintenance
        print("Seeding Maintenance...")
        for i in range(10):
            st = random.choice(stations)
            m = MaintenanceRecord(
                entity_type="station",
                entity_id=st.id,
                technician_id=admin.id,
                maintenance_type="preventive",
                description="Routine checkup",
                cost=random.uniform(500, 2000),
                status=random.choice(["completed", "scheduled", "in_progress"]),
                performed_at=datetime.now(UTC) - timedelta(days=random.randint(1, 30))
            )
            session.add(m)
        session.commit()

        print("Seeding Complete!")

if __name__ == "__main__":
    seed_data()
