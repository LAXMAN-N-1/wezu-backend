from app.db.session import engine
from sqlalchemy import text
from sqlmodel import SQLModel

def drop_all():
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()
    print("Dropped and recreated public schema.")

if __name__ == "__main__":
    drop_all()
