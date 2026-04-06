import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import text
from app.db.session import engine

def dump_dealers():
    with engine.connect() as conn:
        print("--- ALL DEALER PROFILES ---")
        try:
            res = conn.execute(text("SELECT id, user_id, contact_email FROM core.dealer_profiles")).fetchall()
            for row in res:
                print(f"dealer_profiles.id = {row[0]}, user_id = {row[1]}, email = {row[2]}")
        except Exception as e:
            print(f"Dealer profiles query failed: {e}")

if __name__ == '__main__':
    dump_dealers()
