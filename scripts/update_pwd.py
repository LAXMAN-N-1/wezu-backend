import os
import sys

# Add the backend app to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import psycopg2
from app.core.security import get_password_hash

db_url = "postgresql://neondb_owner:npg_8gj3tFVnBsoX@ep-cool-night-adhmotv8-pooler.c-2.us-east-1.aws.neon.tech/wezu?sslmode=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Hash the exact password the user wants
    new_hash = get_password_hash("laxman123")
    
    # Update the dealer@wezu.com account in the DB
    cur.execute(
        "UPDATE users SET hashed_password = %s WHERE email = 'dealer@wezu.com';",
        (new_hash,)
    )
    
    if cur.rowcount > 0:
        print("Successfully updated dealer@wezu.com password to 'laxman123' in the database.")
    else:
        print("Could not find dealer@wezu.com in the database to update.")
        
    conn.commit()
    cur.close()
    conn.close()
except Exception as e:
    import traceback
    traceback.print_exc()
