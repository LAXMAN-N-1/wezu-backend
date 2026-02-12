import sys
import os
from sqlalchemy import create_engine, text

# Add current directory to path so we can import app modules
sys.path.append(os.getcwd())

try:
    from app.core.config import settings
    print(f"DEBUG: settings.DATABASE_URL = {settings.DATABASE_URL}")
    
    # Security check: Panic if it looks like NeonDB/Production
    if "neon.tech" in settings.DATABASE_URL or "aws" in settings.DATABASE_URL:
        print("!! WARNING: DATABASE_URL points to a remote/production database !!")
        print("Aborting safety check to prevent accidental operations.")
        sys.exit(1)
        
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print(f"Connection successful: {result.scalar()}")
        
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
