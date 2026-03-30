from sqlmodel import create_engine, Session, text
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_schema():
    engine = create_engine(settings.DATABASE_URL)
    
    with Session(engine) as session:
        print("Applying schema fixes to Neon DB...")
        
        # 1. Add missing column to battery_catalog
        try:
            session.execute(text("ALTER TABLE battery_catalog ADD COLUMN IF NOT EXISTS capacity_ah FLOAT"))
            session.execute(text("UPDATE battery_catalog SET capacity_ah = capacity_mah / 1000.0 WHERE capacity_ah IS NULL AND capacity_mah IS NOT NULL"))
            session.commit()
            print("Added capacity_ah to battery_catalog.")
        except Exception as e:
            print(f"Error adding capacity_ah: {e}")
            session.rollback()

        # 2. Fix enum case in DB
        try:
            # We'll try to add both cases to the enum to be safe
            session.execute(text("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'LATE_FEE'"))
            session.execute(text("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'late_fee'"))
            session.commit()
            print("Synchronized LATE_FEE enum values in DB.")
        except Exception as e:
            print(f"Note: Error altering enum (might already be fixed or not Postgres): {e}")
            session.rollback()

if __name__ == "__main__":
    fix_schema()
