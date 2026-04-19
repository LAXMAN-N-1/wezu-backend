import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(url)
cur = conn.cursor()
try:
    cur.execute("SELECT * FROM user_sessions LIMIT 1")
    print([desc[0] for desc in cur.description])
except Exception as e:
    print(f"Error: {e}")
conn.close()
