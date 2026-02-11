from sqlmodel import Session, create_engine, text
from app.core.config import settings

def migrate_permission_scope():
    engine = create_engine(str(settings.DATABASE_URL))
    with Session(engine) as session:
        # Check if column exists
        try:
             session.exec(text("SELECT scope FROM permissions LIMIT 1"))
             print("Column scope already exists.")
        except Exception:
             session.rollback()
             print("Adding scope column to permissions table...")
             session.exec(text("ALTER TABLE permissions ADD COLUMN scope VARCHAR DEFAULT 'all'"))
             session.commit()
             print("Migration complete.")

if __name__ == "__main__":
    migrate_permission_scope()
