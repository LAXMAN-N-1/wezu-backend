import os
import sys
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Import all models
from app.models import *
from app.models.battery import Battery
from app.models.settlement import Settlement
from app.models.revenue_report import RevenueReport
from app.models.user import User
from app.models.station import Station

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True)

def create_all_tables():
    print("Creating all tables via SQLModel.metadata.create_all...")
    try:
        SQLModel.metadata.create_all(engine)
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_all_tables()
