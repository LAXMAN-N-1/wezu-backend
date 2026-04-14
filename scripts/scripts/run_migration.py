
import sys
import os
from alembic.config import Config
from alembic import command

def run_migration():
    try:
        # Create Alembic configuration object
        alembic_cfg = Config("alembic.ini")
        
        # Set the script location manually if needed, usually 'alembic'
        # alembic_cfg.set_main_option("script_location", "alembic")
        
        # Run the revision command
        print("Generating migration...")
        command.revision(alembic_cfg, message="add_station_lat_lon_indexes", autogenerate=True)
        print("Migration generation complete.")
        
    except Exception as e:
        print(f"Error running migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
