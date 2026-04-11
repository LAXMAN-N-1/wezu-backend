import os
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.database import engine
from sqlmodel import SQLModel

# Import main models to ensure metadata is registered
from app.models.user import User
from app.models.dealer import DealerProfile, DealerApplication
from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental
from app.models.order import Order
from app.models.product import Product
from app.models.rbac import Role, Permission

print("Connecting to DB...")
try:
    SQLModel.metadata.create_all(engine)
    print("✅ Missing tables created successfully!")
except Exception as e:
    print(f"❌ Failed to create tables: {e}")
