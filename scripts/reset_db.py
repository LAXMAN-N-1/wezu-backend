"""Reset the entire database: drop all schemas, public tables, and custom enum types."""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import engine
from sqlalchemy import text

schemas_to_drop = ['core', 'inventory', 'stations', 'rentals', 'finance', 'dealers', 'logistics']

with engine.connect() as conn:
    # Drop all custom schemas
    for schema in schemas_to_drop:
        conn.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE;'))
        print(f'Dropped schema: {schema}')

    # Drop all public tables including alembic_version
    result = conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    ))
    tables = [row[0] for row in result]
    for table in tables:
        conn.execute(text(f'DROP TABLE IF EXISTS public."{table}" CASCADE;'))
        print(f'Dropped public table: {table}')

    # Drop all custom enum types in public schema
    result = conn.execute(text(
        "SELECT typname FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid "
        "WHERE n.nspname = 'public' AND t.typtype = 'e'"
    ))
    enums = [row[0] for row in result]
    for enum_name in enums:
        conn.execute(text(f'DROP TYPE IF EXISTS public."{enum_name}" CASCADE;'))
        print(f'Dropped enum type: {enum_name}')

    conn.commit()
    print(f'\nDatabase reset complete! Dropped {len(schemas_to_drop)} schemas, {len(tables)} tables, {len(enums)} enums.')
