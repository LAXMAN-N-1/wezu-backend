from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_firebase_admin = None
_credentials = None
_messaging = None
_firebase_ready = False
_firebase_init_attempted = False


def _ensure_firebase_initialized() -> bool:
    global _firebase_admin
    global _credentials
    global _messaging
    global _firebase_ready
    global _firebase_init_attempted

    if _firebase_ready:
        return True
    if _firebase_init_attempted:
        return False

    _firebase_init_attempted = True
    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.info("FCM disabled: FIREBASE_CREDENTIALS_PATH is not configured")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except Exception:
        logger.exception("FCM disabled: firebase_admin package is unavailable")
        return False

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
        _firebase_admin = firebase_admin
        _credentials = credentials
        _messaging = messaging
        _firebase_ready = True
        return True
    except Exception:
        logger.exception("FCM initialization failed")
        return False


class FCMService:
    @staticmethod
    def send_push(
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        token = (token or "").strip()
        if not token:
            return False

        if not _ensure_firebase_initialized():
            return False

        try:
            message = _messaging.Message(
                notification=_messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )
            _messaging.send(message)
            return True
        except Exception:
            logger.exception("FCM push send failed")
            return False

    @staticmethod
    def send_multicast(
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not tokens:
            return False

        clean_tokens = sorted({(token or "").strip() for token in tokens if (token or "").strip()})
        if not clean_tokens:
            return False

        if not _ensure_firebase_initialized():
            return False

        try:
            message = _messaging.MulticastMessage(
                notification=_messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                tokens=clean_tokens,
            )
            response = _messaging.send_multicast(message)
            return response.success_count > 0
        except Exception:
            logger.exception("FCM multicast send failed")
            return False

    @staticmethod
    def send_expiry_notification_multicast(tokens: List[str], title: str, body: str, data: dict, priority: str = "high"):
        if not tokens:
            return False
            
        try:
            android_config = messaging.AndroidConfig(
                priority=priority,
                notification=messaging.AndroidNotification(click_action="wezu://swap")
            )
            
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(badge=1, sound="default"),
                )
            )

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                android=android_config,
                apns=apns_config,
                tokens=tokens,
            )
            response = messaging.send_multicast(message)
            return response.success_count > 0
        except Exception as e:
            print(f"FCM Expiry Multicast Error: {e}")
            return False

