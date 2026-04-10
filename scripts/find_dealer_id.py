import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import text
from app.db.session import engine

def find_dealer():
    with engine.connect() as conn:
        try:
            res = conn.execute(text("""
                SELECT d.id as dealer_id, d.user_id, u.email 
                FROM core.dealer_profiles d
                JOIN core.users u ON d.user_id = u.id
                WHERE u.email = 'dealer@wezu.com'
            """)).fetchone()
            print(f"Laxman dealer_profiles.id = {res[0]}, user_id = {res[1]}, email = {res[2]}")
            
            # Why did id=4 fail? Let's see all dealer profiles
            print("\nAll dealer profiles:")
            all_dealers = conn.execute(text("SELECT id, user_id FROM core.dealer_profiles")).fetchall()
            for row in all_dealers:
                print(f"Profile ID: {row[0]}, User ID: {row[1]}")
                
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == '__main__':
    find_dealer()
