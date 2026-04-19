import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("SELECT id, status, user_type FROM users LIMIT 3")
print("User Table After Fix:")
for row in cur.fetchall():
    print(row)
conn.close()
