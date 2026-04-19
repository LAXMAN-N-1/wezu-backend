from __future__ import annotations
import firebase_admin
from firebase_admin import credentials
import logging
import os
from app.core.config import settings

logger = logging.getLogger(__name__)

def init_firebase():
    """
    Safely initialize Firebase Admin SDK.
    Prevents app crash if credentials are missing or invalid.
    """
    try:
        if not firebase_admin._apps:
            cert_path = settings.FIREBASE_CREDENTIALS_PATH
            
            if not cert_path:
                logger.warning("FIREBASE_CREDENTIALS_PATH not set. Firebase features will be disabled.")
                return None
            
            if not os.path.exists(cert_path):
                logger.warning(f"Firebase credentials file not found at {cert_path}. Firebase features will be disabled.")
                return None

            try:
                cred = credentials.Certificate(cert_path)
                app = firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized successfully")
                return app
            except Exception as e:
                logger.warning(f"Firebase initialization failed (invalid service account JSON?): {str(e)}")
                return None
        else:
            return firebase_admin.get_app()
    except Exception as e:
        logger.error(f"Unexpected error during Firebase setup: {str(e)}")
        return None

# Attempt initialization on module load (non-blocking)
firebase_app = init_firebase()
