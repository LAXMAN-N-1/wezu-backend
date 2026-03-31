import sys
from sqlmodel import SQLModel
from app.core.database import engine
from app.models.oauth import BlacklistedToken

def create_table():
    print("Creating blacklisted_tokens table...")
    # Explicitly create only the blacklisted_tokens table
    BlacklistedToken.metadata.create_all(engine, tables=[BlacklistedToken.__table__])
    print("Table created successfully.")

if __name__ == "__main__":
    create_table()
