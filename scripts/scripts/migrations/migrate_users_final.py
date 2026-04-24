from sqlalchemy import text
from app.db.session import engine

def migrate():
    with engine.connect() as conn:
        print("Migrating core.users table...")
        try:
            conn.execute(text("ALTER TABLE core.users ADD COLUMN IF NOT EXISTS last_global_logout_at TIMESTAMP WITHOUT TIME ZONE;"))
            conn.commit()
            print("✅ Column last_global_logout_at added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
