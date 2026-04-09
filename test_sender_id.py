
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_url = "postgresql://neondb_owner:npg_4OSb6iLGUBIZ@ep-orange-bonus-ah60367a-pooler.c-3.us-east-1.aws.neon.tech/Wezu?sslmode=require&channel_binding=require"

try:
    with psycopg.connect(db_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, is_nullable 
                FROM information_schema.columns 
                WHERE table_schema = 'core' 
                AND table_name = 'ticket_messages' 
                AND column_name = 'sender_id';
            """)
            result = cur.fetchone()
            print(f"Column check result: {result}")
except Exception as e:
    print(f"Check failed: {e}")
