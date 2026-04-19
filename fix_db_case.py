import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = LOWER(status), user_type = LOWER(user_type), kyc_status = LOWER(kyc_status)")
    conn.commit()
    print(f"Updated {cur.rowcount} users.")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
