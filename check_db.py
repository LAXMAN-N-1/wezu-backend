import asyncio
from sqlalchemy import text
from app.db.session import engine

def main():
    with engine.connect() as conn:
        print('--- Tables ---')
        res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        for row in res:
            print(row[0])
            
        print('\n--- Types ---')
        res = conn.execute(text("SELECT typname FROM pg_type JOIN pg_namespace ON pg_namespace.oid = pg_type.typnamespace WHERE nspname = 'public'"))
        for row in res:
            if row[0].startswith('_'): continue
            print(row[0])

if __name__ == '__main__':
    main()
