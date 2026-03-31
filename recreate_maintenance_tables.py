import sys
from sqlmodel import Session, SQLModel
from app.core.database import engine
from sqlalchemy import text
from app.models.maintenance import MaintenanceTemplate, MaintenanceSchedule, MaintenanceRecord, StationDowntime

def recreate_tables():
    print("Dropping maintenance tables...")
    try:
        with engine.begin() as conn:
            # Drop tables in proper order or use CASCADE
            conn.execute(text("DROP TABLE IF EXISTS inventory.maintenance_records CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS inventory.maintenance_schedules CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS inventory.maintenance_templates CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS inventory.station_downtimes CASCADE;"))
            print("Tables dropped successfully.")
            
        print("Recreating maintenance tables...")
        # Create them via SQLModel metadata
        MaintenanceTemplate.metadata.create_all(engine, tables=[
            MaintenanceTemplate.__table__,
            MaintenanceSchedule.__table__,
            MaintenanceRecord.__table__,
            StationDowntime.__table__
        ])
        print("Tables recreated successfully with new integer IDs.")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    recreate_tables()
