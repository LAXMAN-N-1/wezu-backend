import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

# We need to revert existing enum values from lowercase to uppercase.
types_to_fix = ['userstatus', 'usertype', 'kycstatus', 'transactionstatus']

for t in types_to_fix:
    cur.execute(f"SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = '{t}'")
    values = [r[0] for r in cur.fetchall()]
    for val in values:
        if val != val.upper():
            sql = f"ALTER TYPE {t} RENAME VALUE '{val}' TO '{val.upper()}';"
            try:
                print(sql)
                cur.execute(sql)
            except Exception as e:
                print(f"Failed {val}: {e}")

print("Done reverting ENUMs!")
conn.close()
