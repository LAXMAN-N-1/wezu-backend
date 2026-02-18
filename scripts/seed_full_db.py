import logging
from sqlmodel import Session, select
from app.db.session import engine
from app.core.security import get_password_hash
# Import ALL models that relate to User to ensure registry is populated
from app.models import (
    User, UserType, UserStatus, Role, Permission, UserRole,
    UserProfile, Station, StationStatus, Battery, BatteryStatus, 
    BatteryHealth, BatteryCatalog, Transaction, Wallet, 
    TransactionType, TransactionStatus, Device, Vehicle, 
    DealerProfile, DriverProfile, StaffProfile
)
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_db():
    with Session(engine) as session:
        logger.info("🌱 Seeding Database...")
        
        # 1. Create Roles
        admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrator", is_system_role=True)
            session.add(admin_role)
            logger.info("Created Admin Role")
            
        dealer_role = session.exec(select(Role).where(Role.name == "dealer")).first()
        if not dealer_role:
            dealer_role = Role(name="dealer", description="Dealer/Franchise Owner")
            session.add(dealer_role)
            logger.info("Created Dealer Role")

        customer_role = session.exec(select(Role).where(Role.name == "customer")).first()
        if not customer_role:
            customer_role = Role(name="customer", description="End User")
            session.add(customer_role)
            logger.info("Created Customer Role")
            
        session.commit()
        session.refresh(admin_role)
        session.refresh(dealer_role)

        # 2. Create Users
        # Admin
        admin_user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not admin_user:
            admin_user = User(
                email="admin@wezu.com",
                phone_number="9999999999",
                full_name="Super Admin",
                hashed_password=get_password_hash("admin123"),
                user_type=UserType.ADMIN,
                is_superuser=True,
                role_id=admin_role.id
            )
            session.add(admin_user)
            logger.info("Created Admin User")
        
        # Dealer
        dealer_user = session.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if not dealer_user:
            dealer_user = User(
                email="dealer@wezu.com",
                phone_number="8888888888",
                full_name="Hyderabad Dealer",
                hashed_password=get_password_hash("dealer123"),
                user_type=UserType.DEALER,
                role_id=dealer_role.id
            )
            session.add(dealer_user)
            logger.info("Created Dealer User")
            
        # Customer (Demo)
        customer = session.exec(select(User).where(User.phone_number == "9646852893")).first()
        if not customer:
            customer = User(
                email="customer@wezu.com",
                phone_number="9646852893",
                full_name="Demo Customer",
                hashed_password=get_password_hash("123456"),
                user_type=UserType.CUSTOMER,
                role_id=customer_role.id
            )
            session.add(customer)
            logger.info("Created Customer User")
            
        session.commit()
        session.refresh(dealer_user)
        session.refresh(customer)
        
        # 3. Create Wallets
        if not session.exec(select(Wallet).where(Wallet.user_id == customer.id)).first():
            wallet = Wallet(user_id=customer.id, balance=500.0)
            session.add(wallet)

        # 4. Create Battery Catalog (SKUs)
        sku_lithium = session.exec(select(BatteryCatalog).where(BatteryCatalog.name == "Wezu Pro 72V")).first()
        if not sku_lithium:
            sku_lithium = BatteryCatalog(
                name="Wezu Pro 72V",
                brand="Wezu",
                model="LFP-72-40",
                capacity_mah=40000,
                voltage=72.0,
                price_per_day=150.0,
                price_full_purchase=85000.0,
                description="High performance LFP battery for heavy duty use.",
                image_url="https://images.unsplash.com/photo-1620619767323-b95a89183081?q=80&w=2940&auto=format&fit=crop"
            )
            session.add(sku_lithium)
            session.commit()
            session.refresh(sku_lithium)
            logger.info("Created Wezu Pro 72V SKU")
            
        sku_std = session.exec(select(BatteryCatalog).where(BatteryCatalog.name == "Wezu Standard 60V")).first()
        if not sku_std:
            sku_std = BatteryCatalog(
                name="Wezu Standard 60V",
                brand="Wezu",
                model="NMC-60-30",
                capacity_mah=30000,
                voltage=60.0,
                price_per_day=100.0,
                price_full_purchase=60000.0,
                description="Standard NMC battery for daily commute.",
                image_url="https://images.unsplash.com/photo-1620619767323-b95a89183081?q=80&w=2940&auto=format&fit=crop"
            )
            session.add(sku_std)
            session.commit()
            session.refresh(sku_std)
            logger.info("Created Wezu Standard 60V SKU")

        # 5. Create Stations & Batteries
        stations_data = [
            {"name": "Hitech City Hub", "lat": 17.4474, "lng": 78.3762, "address": "Madhapur, Hyderabad"},
            {"name": "Gachibowli PowerPt", "lat": 17.4401, "lng": 78.3489, "address": "Gachibowli, Hyderabad"},
            {"name": "Kondapur Center", "lat": 17.4622, "lng": 78.3568, "address": "Kondapur, Hyderabad"},
            {"name": "Jubilee Hills Stn", "lat": 17.4325, "lng": 78.4070, "address": "Jubilee Hills, Hyderabad"},
            {"name": "Banjara Hills Stn", "lat": 17.4126, "lng": 78.4397, "address": "Banjara Hills, Hyderabad"},
        ]
        
        for idx, st_data in enumerate(stations_data):
            station = session.exec(select(Station).where(Station.name == st_data["name"])).first()
            if not station:
                station = Station(
                    name=st_data["name"],
                    latitude=st_data["lat"],
                    longitude=st_data["lng"],
                    address=st_data["address"],
                    owner_id=dealer_user.id,
                    total_slots=10,
                    available_slots=5,
                    available_batteries=5,
                    status=StationStatus.OPERATIONAL,
                    image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&q=80&w=2072"
                )
                session.add(station)
                session.commit()
                session.refresh(station)
                logger.info(f"Created Station: {station.name}")
                
                # Add Batteries to Station
                for b_idx in range(5):
                    sku = sku_lithium if b_idx % 2 == 0 else sku_std
                    sn = f"WZ-{idx}-{b_idx}-{int(datetime.utcnow().timestamp())}"
                    
                    batt = Battery(
                        serial_number=sn,
                        sku_id=sku.id,
                        station_id=station.id,
                        status=BatteryStatus.AVAILABLE,
                        health_status=BatteryHealth.GOOD,
                        current_charge=95.0 - (b_idx * 5),
                        cycle_count=10 + b_idx
                    )
                    session.add(batt)
                session.commit()

        logger.info("✅ Database Seeding Complete!")

if __name__ == "__main__":
    seed_db()
