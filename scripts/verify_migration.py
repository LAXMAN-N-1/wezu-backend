import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def verify():
    print(f"Connecting to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 1. Check Batteries ID type
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'batteries' AND column_name = 'id';")
        res = cur.fetchone()
        print(f"Batteries ID: {res}")
        
        # 2. Check Station Cameras table
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'station_cameras';")
        res = cur.fetchone()
        print(f"Station Cameras Table exists: {res[0] > 0}")
        
        # 3. Check some columns in station_cameras
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'station_cameras';")
        cols = cur.fetchall()
        print(f"Station Cameras Columns: {[c[0] for c in cols]}")
        
        # 4. Check if batteries.status is Enum (should show 'USER-DEFINED')
        cur.execute("SELECT data_type, udt_name FROM information_schema.columns WHERE table_name = 'batteries' AND column_name = 'status';")
        res = cur.fetchone()
        print(f"Batteries Status Type: {res}")
        
        cur.close()
        conn.close()
        print("Verification completed successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
