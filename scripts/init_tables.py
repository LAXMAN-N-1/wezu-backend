import os
import sys
# Add the parent directory to sys.path to allow importing from app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import create_engine
from app.core.config import settings
from app.db.session import engine
from sqlmodel import SQLModel

# Import main models to ensure metadata is registered
from app.models.user import User
from app.models.dealer import DealerProfile, DealerApplication
from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental
from app.models.rbac import Role, Permission

print("Connecting to DB...")
try:
    SQLModel.metadata.create_all(engine)
    print("SUCCESS: Missing tables created successfully!")
except Exception as e:
    print(f"ERROR: Failed to create tables: {e}")
