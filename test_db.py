import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
try:
    print(f"Connecting to {url.split('@')[1]}...")
    conn = psycopg2.connect(url, connect_timeout=10)
    print("Success!")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
