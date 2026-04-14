from sqlalchemy import text
from app.db.session import engine

def migrate():
    with engine.connect() as conn:
        print("Migrating users table...")
        conn.execute(text("ALTER TABLE core.users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        conn.execute(text("UPDATE core.users SET is_active = TRUE WHERE is_active IS NULL;"))
        conn.commit()
        print("✅ Migration complete.")

if __name__ == "__main__":
    migrate()
