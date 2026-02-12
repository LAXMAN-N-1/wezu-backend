"""
Comprehensive Database Table Verification Script
Checks: table existence, column schemas, foreign keys, basic CRUD readiness
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import SQLModel, text, Session
from app.core.config import settings
from app.models import *  # Import all models to register metadata
from sqlalchemy import create_engine, inspect

def main():
    print("=" * 70)
    print("WEZU BACKEND — DATABASE TABLE VERIFICATION")
    print("=" * 70)

    # 1. Connect to Database
    print(f"\n📡 Connecting to: {settings.DATABASE_URL[:40]}...")
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful!\n")
    except Exception as e:
        print(f"❌ Database connection FAILED: {e}")
        sys.exit(1)

    inspector = inspect(engine)

    # 2. Get expected tables from SQLModel metadata
    expected_tables = sorted(SQLModel.metadata.tables.keys())
    print(f"📋 Models define {len(expected_tables)} tables:")
    for t in expected_tables:
        print(f"   • {t}")

    # 3. Get actual tables in the database
    actual_tables = sorted(inspector.get_table_names())
    print(f"\n📦 Database has {len(actual_tables)} tables:")
    for t in actual_tables:
        print(f"   • {t}")

    # 4. Compare: Missing and Extra tables
    missing = set(expected_tables) - set(actual_tables)
    extra = set(actual_tables) - set(expected_tables)

    print("\n" + "=" * 70)
    print("TABLE COMPARISON")
    print("=" * 70)

    if missing:
        print(f"\n❌ MISSING TABLES ({len(missing)}) — defined in models but NOT in DB:")
        for t in sorted(missing):
            print(f"   ⚠️  {t}")
    else:
        print("\n✅ All model tables exist in the database!")

    if extra:
        print(f"\n📝 EXTRA TABLES ({len(extra)}) — in DB but NOT in models (migrations, alembic, etc.):")
        for t in sorted(extra):
            print(f"   ℹ️  {t}")

    # 5. Schema Comparison: columns in model vs DB for each matching table
    common_tables = set(expected_tables) & set(actual_tables)
    schema_issues = []
    
    print("\n" + "=" * 70)
    print("COLUMN SCHEMA VERIFICATION")
    print("=" * 70)
    
    for table_name in sorted(common_tables):
        model_table = SQLModel.metadata.tables[table_name]
        model_columns = {col.name: str(col.type) for col in model_table.columns}
        
        db_columns_info = inspector.get_columns(table_name)
        db_columns = {col['name']: str(col['type']) for col in db_columns_info}
        
        missing_cols = set(model_columns.keys()) - set(db_columns.keys())
        extra_cols = set(db_columns.keys()) - set(model_columns.keys())
        
        if missing_cols or extra_cols:
            schema_issues.append(table_name)
            print(f"\n⚠️  {table_name}:")
            if missing_cols:
                for c in sorted(missing_cols):
                    print(f"      ❌ Missing column: {c} ({model_columns[c]})")
            if extra_cols:
                for c in sorted(extra_cols):
                    print(f"      ➕ Extra column in DB: {c} ({db_columns[c]})")
    
    if not schema_issues:
        print("\n✅ All columns match between models and database!")
    else:
        print(f"\n⚠️  {len(schema_issues)} table(s) have column mismatches")

    # 6. Foreign Key Verification
    print("\n" + "=" * 70)
    print("FOREIGN KEY VERIFICATION")
    print("=" * 70)
    
    fk_issues = []
    for table_name in sorted(common_tables):
        db_fks = inspector.get_foreign_keys(table_name)
        for fk in db_fks:
            ref_table = fk['referred_table']
            if ref_table not in actual_tables:
                fk_issues.append((table_name, fk['constrained_columns'], ref_table))
                print(f"  ❌ {table_name}.{fk['constrained_columns']} → {ref_table} (table doesn't exist!)")
    
    if not fk_issues:
        print("\n✅ All foreign keys reference valid tables!")
    
    # 7. Row counts (quick health check)
    print("\n" + "=" * 70)
    print("TABLE ROW COUNTS")
    print("=" * 70)
    
    with Session(engine) as session:
        for table_name in sorted(common_tables):
            try:
                result = session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                count = result.scalar()
                status = "📊" if count > 0 else "📭"
                print(f"  {status} {table_name}: {count} rows")
            except Exception as e:
                print(f"  ❌ {table_name}: ERROR — {e}")
                session.rollback()

    # 8. Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Models defined:       {len(expected_tables)}")
    print(f"  Tables in DB:         {len(actual_tables)}")
    print(f"  Missing tables:       {len(missing)}")
    print(f"  Schema mismatches:    {len(schema_issues)}")
    print(f"  FK issues:            {len(fk_issues)}")
    
    if not missing and not schema_issues and not fk_issues:
        print("\n🎉 ALL CHECKS PASSED — Database is in sync with models!")
    else:
        print("\n⚠️  ISSUES FOUND — See details above")
        if missing:
            print("  💡 Run 'alembic upgrade head' or use init_db() to create missing tables")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
