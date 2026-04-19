import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(url)
cur = conn.cursor()

for t in ['userstatus', 'usertype', 'kycstatus', 'transactionstatus']:
    cur.execute(f"SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = '{t}'")
    cols = [r[0] for r in cur.fetchall()]
    print(f"{t}: {cols}")

conn.close()
