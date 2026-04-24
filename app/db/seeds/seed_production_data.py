from __future__ import annotations
from sqlmodel import Session, select
from app.models.user import User, KYCStatus
from app.models.rbac import Role, Permission
from app.models.battery import Battery, BatteryStatus
from app.models.station import Station, StationSlot, StationStatus
from app.db.session import engine, init_db
from app.models.warehouse import Warehouse
from app.models.financial import Wallet
from app.core.security import get_password_hash
from datetime import datetime

def seed_data():
    # 0. Initialize Database (Create Schemas & Tables)
    print("Initializing database schemas and tables...")
    init_db()
    
    with Session(engine) as session:
        # 1. Seed Roles & Permissions are already handled by init_db()

        # 2. Seed Admin User
        admin_user = session.exec(select(User).where(User.email == "admin@wezu.energy")).first()
        if not admin_user:
            admin_user = User(
                email="admin@wezu.energy",
                phone_number="+910000000000",
                full_name="System Administrator",
                hashed_password=get_password_hash("Admin@123"),
                is_superuser=True,
                kyc_status=KYCStatus.APPROVED
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            
            # Initial Wallet
            session.add(Wallet(user_id=admin_user.id, balance=1000000.0))

        # 3. Seed Warehouses (Logistics)
        main_wh = Warehouse(
            name="Bengaluru Central Hub",
            code="WH-BLR-001",
            address="Peenya Industrial Area, Block 4",
            city="Bengaluru",
            state="Karnataka",
            pincode="560058",
            is_active=True
        )
        session.add(main_wh)
        session.commit()
        session.refresh(main_wh)

        # 4. Seed Infrastructure (Stations & Slots)
        station1 = Station(
            name="WEZU Station - Indiranagar",
            address="100 Feet Rd, Indiranagar, Bengaluru",
            city="Bengaluru",
            latitude=12.9784,
            longitude=77.6408,
            total_slots=8,
            status=StationStatus.ACTIVE
        )
        session.add(station1)
        session.commit()
        session.refresh(station1)
        
        for i in range(1, 9):
            slot = StationSlot(
                station_id=station1.id,
                slot_number=i,
                status="ready" if i <= 4 else "empty"
            )
            session.add(slot)

        # 5. Seed Inventory (Batteries)
        for i in range(1, 11):
            battery = Battery(
                serial_number=f"WZB-2026-{i:03d}",
                status=BatteryStatus.AVAILABLE,
                current_charge=95.0,
                health_percentage=98.5,
                warehouse_id=main_wh.id,
                current_user_id=None
            )
            session.add(battery)

        session.commit()
        print("Production reference data seeded successfully in namespaced schemas.")

if __name__ == "__main__":
    seed_data()
