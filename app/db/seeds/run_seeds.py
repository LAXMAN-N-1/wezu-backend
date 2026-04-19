from __future__ import annotations
"""Run all seed scripts to populate database."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlmodel import SQLModel
from app.core.database import engine, get_db
import app.models.all  # noqa: F401  # Import all models to register tables

def run_seeds():
    # Create all tables
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    print("✅ Tables created/verified")

    # Run seeds
    from app.db.seeds.seed_cms import seed_cms
    from app.db.seeds.seed_modules import seed_all_modules
    from app.db.seeds.seed_logistics_warehouse_manager import (
        seed as seed_logistics_warehouse_manager,
    )

    # Ensure logistics login credentials are available even when non-critical
    # CMS/module seeds fail due optional schema drift.
    seed_logistics_warehouse_manager()

    from sqlmodel import Session
    with Session(engine) as session:
        try:
            seed_cms(session)
        except Exception as exc:
            print(f"⚠ seed_cms failed: {exc}")
            session.rollback()
        try:
            seed_all_modules(session)
        except Exception as exc:
            print(f"⚠ seed_all_modules failed: {exc}")
            session.rollback()
    print("\n🎉 All seeds completed!")

if __name__ == "__main__":
    run_seeds()
