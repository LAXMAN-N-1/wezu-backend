from sqlalchemy import text
from app.db.session import engine

def check_counts():
    with engine.connect() as conn:
        try:
            res1 = conn.execute(text("SELECT COUNT(*) FROM core.users;")).scalar()
            print(f"core.users count: {res1}")
        except Exception as e:
            print(e)
            
        try:
            res2 = conn.execute(text("SELECT COUNT(*) FROM admin_users;")).scalar()
            print(f"admin_users count: {res2}")
        except Exception as e:
            print(e)

if __name__ == "__main__":
    check_counts()
