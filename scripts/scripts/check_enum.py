import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from sqlalchemy import text

def check_enum():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'userstatus'")).fetchall()
        print("userstatus:", [r[0] for r in res])
        res2 = conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'usertype'")).fetchall()
        print("usertype:", [r[0] for r in res2])

if __name__ == "__main__":
    check_enum()
