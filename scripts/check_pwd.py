import os
import sys

# Add the backend app to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import psycopg2
from app.core.security import verify_password

db_url = "postgresql://neondb_owner:npg_8gj3tFVnBsoX@ep-cool-night-adhmotv8-pooler.c-2.us-east-1.aws.neon.tech/wezu?sslmode=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT hashed_password FROM users WHERE email = 'dealer@wezu.com';")
    pwd_row = cur.fetchone()
    if pwd_row:
        pwd = pwd_row[0]
        test_pwds = ["password", "password123", "laxman123", "dealer123", "admin123"]
        for p in test_pwds:
            if verify_password(p, pwd):
                print(f"MATCH FOUND for dealer@wezu.com: {p}")
                break
        else:
            print("No matching password found among test passwords.")
    else:
        print("User not found.")
        
    cur.execute("SELECT hashed_password FROM users WHERE email = 'dealer_extra_1@wezutest.com';")
    pwd_row = cur.fetchone()
    if pwd_row:
        pwd = pwd_row[0]
        for p in test_pwds:
            if verify_password(p, pwd):
                print(f"MATCH FOUND for dealer_extra_1@wezutest.com: {p}")
                break
except Exception as e:
    import traceback
    traceback.print_exc()
