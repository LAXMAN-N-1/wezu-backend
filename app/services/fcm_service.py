import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings
from typing import List, Optional

from app.core.firebase import firebase_app

class FCMService:
    @staticmethod
    def send_push(token: str, title: str, body: str, data: Optional[dict] = None):
        if not token: 
            return False
            
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )
            response = messaging.send(message)
            return True
        except Exception as e:
            print(f"FCM Error: {e}")
            return False

    @staticmethod
    def send_multicast(tokens: List[str], title: str, body: str, data: Optional[dict] = None):
        if not tokens:
            return False
            
        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                tokens=tokens,
            )
            response = messaging.send_multicast(message)
            return response.success_count > 0
        except Exception as e:
            print(f"FCM Multicast Error: {e}")
            return False
