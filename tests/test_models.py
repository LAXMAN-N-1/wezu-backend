import sys
import os
import traceback

from sqlmodel import SQLModel
# Add '.' to sys.path so 'app' can be imported
sys.path.insert(0, os.path.abspath('.'))

try:
    from app.models.user import User
    from app.models.notification_preference import NotificationPreference
    # Try importing typical database configuration to trigger all models to load
    from app.core.database import engine
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    print("All mappers configured successfully!")
except Exception as e:
    print("Error configuring mappers:")
    traceback.print_exc()
