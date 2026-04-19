import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT id, email, status, user_type, kyc_status FROM users LIMIT 10")
    for row in cur.fetchall():
        print(row)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
