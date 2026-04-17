from app.db.session import engine
from sqlalchemy import text

def inspect_schema():
    print("Inspecting database schema...")
    with engine.connect() as conn:
        # Check batteries.id
        res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'batteries' AND column_name = 'id'")).fetchone()
        print(f"batteries.id: {res}")
        
        # Check station_slots.battery_id
        res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'station_slots' AND column_name = 'battery_id'")).fetchone()
        print(f"station_slots.battery_id: {res}")

        # Check stations.id
        res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'stations' AND column_name = 'id'")).fetchone()
        print(f"stations.id: {res}")

if __name__ == "__main__":
    inspect_schema()
