import asyncio
from sqlalchemy import text
from app.db.session import engine

def main():
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        print("Dropping table test_reports if exists...")
        conn.execute(text("DROP TABLE IF EXISTS test_reports CASCADE"))
        
        print("Dropping alembic_version if exists...")
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        
        print("Dropping Types...")
        res = conn.execute(text("SELECT typname FROM pg_type JOIN pg_namespace ON pg_namespace.oid = pg_type.typnamespace WHERE nspname = 'public'"))
        types_to_drop = [row[0] for row in res if not row[0].startswith('_')]
        
        for typ in types_to_drop:
            print(f"Dropping type {typ}")
            try:
                conn.execute(text(f'DROP TYPE IF EXISTS "{typ}" CASCADE'))
            except Exception as e:
                print(f"Error dropping {typ}: {e}")

if __name__ == '__main__':
    main()
