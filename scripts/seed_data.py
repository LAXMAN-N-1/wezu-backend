import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery
from app.models.ecommerce import EcommerceProduct as Product
from app.models.staff import StaffProfile
import app.models

from app.core.security import get_password_hash

def seed_data():
    with Session(engine) as session:
        print("Seeding data...")

        # Create Superuser
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not user:
            superuser = User(
                email="admin@wezu.com",
                full_name="Super Admin",
                phone_number="0000000000",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_superuser=True
            )
            session.add(superuser)
            print("Created superuser.")
        else:
            print("Superuser already exists.")

        # Create Station
        station = session.exec(select(Station).where(Station.name == "Central Station")).first()
        if not station:
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
            print("Created station.")
        else:
            print("Station already exists.")

        # Create Batteries
        # Only create if station exists (either newly created or fetched)
        if station and station.id:
            for i in range(5):
                serial_number = f"BAT-{1000+i}"
                if not session.exec(select(Battery).where(Battery.serial_number == serial_number)).first():
                    battery = Battery(
                        serial_number=serial_number,
                        model="Li-Ion-2024",
                        capacity_ah=2.5,
                        status="available",
                        current_charge=100.0,
                        health_percentage=100.0,
                        station_id=station.id
                    )
                    session.add(battery)
                    print(f"Created battery {serial_number}.")
                else:
                    print(f"Battery {serial_number} already exists.")

        # Create Product
        product_sku = "LION-PACK-001"
        if not session.exec(select(Product).where(Product.sku == product_sku)).first():
            product = Product(
                name="Lithium Ion Battery Pack",
                sku=product_sku,
                price=15000.0,
                stock_quantity=50,
                category="battery",
                description="High performance battery pack"
            )
            session.add(product)
            print("Created product.")
        else:
            print("Product already exists.")

        session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    seed_data()
