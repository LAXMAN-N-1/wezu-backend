import sys
import os
import traceback

sys.path.insert(0, os.path.abspath('.'))

try:
    from app.api.v1.users import get_notification_preferences, update_notification_preferences
    from app.api.v1.profile import get_preferences, update_preferences
    print("Endpoints imported successfully!")
except Exception as e:
    print("Error importing endpoints:")
    traceback.print_exc()
