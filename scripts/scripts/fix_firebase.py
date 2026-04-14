import os

integrations_path = 'app/integrations/firebase.py'
with open(integrations_path, 'r') as f:
    content = f.read()

# Fix imports
if 'from app.core.firebase import firebase_app' not in content:
    content = content.replace('from app.core.config import settings', 'from app.core.config import settings\nfrom app.core.firebase import firebase_app')

# Simplify __init__
import re
pattern = r'def __init__\(self\):.*?def send_notification'
replacement = '''def __init__(self):
        # Initialization handled by app.core.firebase
        self._app = firebase_app
        if not self._app:
            logger.warning("FirebaseIntegration initialized without active Firebase app.")
    
    def send_notification'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open(integrations_path, 'w') as f:
    f.write(content)

print(f"Fixed {integrations_path}")

# Fix fcm_service.py
fcm_path = 'app/services/fcm_service.py'
with open(fcm_path, 'r') as f:
    content = f.read()

# Replace local init with core
fcm_replacement = '''from app.core.firebase import firebase_app

class FCMService:'''
pattern_fcm = r'# Initialize Firebase.*?class FCMService:'
content = re.sub(pattern_fcm, fcm_replacement, content, flags=re.DOTALL)

with open(fcm_path, 'w') as f:
    f.write(content)

print(f"Fixed {fcm_path}")
