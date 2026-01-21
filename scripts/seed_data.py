import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery
from app.models.ecommerce import Product
from app.core.security import get_password_hash

def seed_data():
    with Session(engine) as session:
        # Check if data exists
        if session.exec(select(User)).first():
            print("Data already seeded.")
            return

        print("Seeding data...")

        # Create Superuser
        superuser = User(
            email="admin@wezu.com",
            full_name="Super Admin",
            phone_number="0000000000",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True
        )
        session.add(superuser)

        # Create Station
        station = Station(
            name="Central Station",
            address="123 Main St, Bangalore",
            latitude=12.9716,
            longitude=77.5946,
            total_slots=10,
            available_slots=5,
            is_active=True
        )
        session.add(station)
        session.flush() # get ID

        # Create Batteries
        for i in range(5):
            battery = Battery(
                serial_number=f"BAT-{1000+i}",
                status="available",
                charge_level=100.0,
                health_status="good",
                station_id=station.id
            )
            session.add(battery)

        # Create Product
        product = Product(
            name="Lithium Ion Battery Pack",
            sku="LION-PACK-001",
            price=15000.0,
            stock_quantity=50,
            category="battery",
            description="High performance battery pack"
        )
        session.add(product)

        session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    seed_data()
