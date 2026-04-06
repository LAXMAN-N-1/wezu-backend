import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import text
from app.db.session import engine

def kill_locks():
    with engine.connect() as conn:
        print("Killing blocking queries...")
        try:
            conn.execute(text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE pid <> pg_backend_pid()
                AND state = 'active'
                AND wait_event_type = 'Lock';
            """))
            print("Done")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    kill_locks()
