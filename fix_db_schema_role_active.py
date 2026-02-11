from sqlmodel import Session, create_engine, text
from app.core.config import settings

def migrate_role_is_active():
    engine = create_engine(str(settings.DATABASE_URL))
    with Session(engine) as session:
        # Check if column exists
        try:
             session.exec(text("SELECT is_active FROM roles LIMIT 1"))
             print("Column is_active already exists.")
        except Exception:
             session.rollback() # Fix transaction state
             print("Adding is_active column to roles table...")
             session.exec(text("ALTER TABLE roles ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
             session.commit()
             print("Migration complete.")

if __name__ == "__main__":
    migrate_role_is_active()
