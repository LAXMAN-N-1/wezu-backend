import sys
import os

# Set up paths to include the app directory
base_dir = r"C:\Users\kamboja Srilaxmi\OneDrive\Desktop\wezu\wezu-backend"
sys.path.append(base_dir)

try:
    from app.db.session import init_db
    print("Attempting to initialize database (this triggers mapper configuration)...")
    # We won't actually call create_all if we can't connect, 
    # but the import and basic setup should trigger the error if it still exists.
    # Actually, SQLAlchemy configures mappers when they are first used.
    from app.models.user import User
    from app.models.token import SessionToken
    from sqlalchemy.orm import configure_mappers
    
    configure_mappers()
    print("Success: SQLAlchemy mappers configured successfully!")
except Exception as e:
    print(f"Error during verification: {e}")
    sys.exit(1)
