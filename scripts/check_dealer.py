import os
import psycopg2

db_url = "postgresql://neondb_owner:npg_8gj3tFVnBsoX@ep-cool-night-adhmotv8-pooler.c-2.us-east-1.aws.neon.tech/wezu?sslmode=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT email, full_name, user_type FROM users WHERE user_type = 'DEALER';")
    rows = cur.fetchall()
    print("Dealers in DB:")
    for row in rows:
        print(row)
    cur.close()
    conn.close()
except Exception as e:
    print(e)
