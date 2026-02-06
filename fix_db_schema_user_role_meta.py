
from sqlmodel import Session, create_engine, text
from app.core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as session:
        print("Migrating user_roles schema...")
        
        # Add columns if they don't exist
        # PostgreSQL syntax
        statements = [
            "ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS assigned_by INTEGER REFERENCES admin_users(id)",
            "ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS effective_from TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')",
            "ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE",
            "ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')"
        ]
        
        for stmt in statements:
            try:
                session.exec(text(stmt))
                session.commit()
                print(f"Executed: {stmt}")
            except Exception as e:
                print(f"Error executing {stmt}: {e}")
                session.rollback()
                
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
