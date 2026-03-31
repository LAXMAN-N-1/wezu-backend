"""Run all seed scripts to populate database."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlmodel import SQLModel
from app.core.database import engine, get_db
from app.models import *  # Import all models to register tables

def run_seeds():
    # Create all tables
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    print("✅ Tables created/verified")

    # Run seeds
    from app.db.seeds.seed_cms import seed_cms
    from app.db.seeds.seed_modules import seed_all_modules

    from sqlmodel import Session
    with Session(engine) as session:
        seed_cms(session)
        seed_all_modules(session)
    print("\n🎉 All seeds completed!")

if __name__ == "__main__":
    run_seeds()
