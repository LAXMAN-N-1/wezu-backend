import os
import sys

# Try different python paths before continuing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel, create_engine
from app.core.config import settings

def create_table():
    print(f"Creating tables for engine: {settings.DATABASE_URL}")
    engine = create_engine(str(settings.DATABASE_URL))

    # Import explicit models directly
    from app.models.dealer_stock_request import DealerStockRequest
    from app.models.battery_catalog import BatteryCatalog
    from app.models.user import User
    from app.models.dealer import DealerProfile
    
    # This will only create missing tables
    SQLModel.metadata.create_all(engine)
    print("Successfully created dealer_stock_requests table.")
    
    # Let's also resolve the charging_queue foreign key violation
    # by deleting orphaned charging queues where battery_id not in batteries
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM charging_queue WHERE battery_id NOT IN (SELECT id FROM batteries);"))
            conn.commit()
            print("Successfully deleted orphaned charging_queue rows.")
    except Exception as e:
        print(f"Failed to delete orphaned charging queues: {e}")

if __name__ == "__main__":
    create_table()
