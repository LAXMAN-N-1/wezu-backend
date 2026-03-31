"""Create the missing rentals.swap_sessions table."""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import SQLModel
from app.db.session import engine
from app.models.swap import SwapSession  # noqa: F401

# Ensure the rentals schema exists
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS rentals"))
    conn.commit()

# Create the swap_sessions table
SwapSession.metadata.create_all(engine, tables=[SwapSession.__table__])
print("✅ rentals.swap_sessions table created successfully!")
