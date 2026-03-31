import sys
from sqlmodel import Session, text
from app.core.database import engine

def add_column():
    print("Adding last_global_logout_at column to users table...")
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE core.users ADD COLUMN last_global_logout_at TIMESTAMP WITHOUT TIME ZONE;"))
            print("Column added successfully.")
    except Exception as e:
        if "already exists" in str(e):
            print("Column already exists.")
        else:
            print(f"Error: {e}")

if __name__ == "__main__":
    add_column()
