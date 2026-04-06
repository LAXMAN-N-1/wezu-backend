import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import text
from app.db.session import engine

def run_checks():
    with engine.connect() as conn:
        print("--- CHECK 1: Total Batteries ---")
        try:
            res1 = conn.execute(text("SELECT COUNT(*) as total_batteries FROM batteries")).scalar()
            print(f"Total in batteries table: {res1}")
        except Exception as e:
            conn.rollback()
            print(f"Query on batteries failed: {e}")

        print("\n--- CHECK 2: Distribution ---")
        try:
            res2 = conn.execute(text("""
                SELECT location_type, station_id, COUNT(*) as count
                FROM batteries
                GROUP BY location_type, station_id
            """)).fetchall()
            for row in res2:
                print(f"Location: {row[0]}, Station: {row[1]}, Count: {row[2]}")
        except Exception as e:
            conn.rollback()
            print(f"Distribution query failed: {e}")

        print("\n--- CHECK 3: wezu_battery schema tables ---")
        try:
            res3 = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'wezu_battery'
            """)).fetchall()
            if not res3:
                print("No tables found in wezu_battery schema.")
            else:
                for row in res3:
                    print(row[0])
        except Exception as e:
            conn.rollback()
            print(f"wezu_battery schema query failed: {e}")

if __name__ == '__main__':
    run_checks()
