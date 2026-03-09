"""
Firebase Cloud Messaging Integration
Handles push notifications to mobile devices
"""
import firebase_admin
from firebase_admin import credentials, messaging
from typing import List, Dict, Any, Optional
from app.core.config import settings
import logging
import json

logger = logging.getLogger(__name__)


class FirebaseIntegration:
    """Firebase Cloud Messaging wrapper"""
    
    def __init__(self):
        try:
            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                if not settings.FIREBASE_CREDENTIALS_PATH:
                    logger.warning("FIREBASE_CREDENTIALS_PATH not set. Push notifications will be disabled.")
                    return
                
                import os
                if not os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                    logger.warning(f"Firebase credentials file not found at {settings.FIREBASE_CREDENTIALS_PATH}. Push notifications will be disabled.")
                    return

                try:
                    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase initialized successfully")
                except Exception as e:
                    logger.warning(f"Firebase initialization failed (likely invalid service account JSON): {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during Firebase setup: {str(e)}")
    
    def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Send push notification to a single device
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL
            
        Returns:
            Message ID if successful
        """
        try:
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            message = messaging.Message(
                notification=notification,
                data=data or {},
                token=token
            )
            
            response = messaging.send(message)
            logger.info(f"Notification sent successfully: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return None
    
    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send notification to multiple devices
        
        Args:
            tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            Response with success/failure counts
        """
        try:
            notification = messaging.Notification(
                title=title,
                body=body
            )
            
            message = messaging.MulticastMessage(
                notification=notification,
                data=data or {},
                tokens=tokens
            )
            
            response = messaging.send_multicast(message)
            logger.info(
                f"Multicast sent: {response.success_count} successful, "
                f"{response.failure_count} failed"
            )
            
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "responses": [
                    {
                        "success": resp.success,
                        "message_id": resp.message_id if resp.success else None,
                        "error": str(resp.exception) if not resp.success else None
                    }
                    for resp in response.responses
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to send multicast: {str(e)}")
            return {
                "success_count": 0,
                "failure_count": len(tokens),
                "error": str(e)
            }
    
    def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Send notification to a topic
        
        Args:
            topic: Topic name
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            Message ID if successful
        """
        try:
            notification = messaging.Notification(
                title=title,
                body=body
            )
            
            message = messaging.Message(
                notification=notification,
                data=data or {},
                topic=topic
            )
            
            response = messaging.send(message)
            logger.info(f"Topic notification sent: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send topic notification: {str(e)}")
            return None
    
    def subscribe_to_topic(
        self,
        tokens: List[str],
        topic: str
    ) -> Dict[str, Any]:
        """
        Subscribe devices to a topic
        
        Args:
            tokens: List of device tokens
            topic: Topic name
            
        Returns:
            Response with success/failure counts
        """
        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            logger.info(
                f"Topic subscription: {response.success_count} successful, "
                f"{response.failure_count} failed"
            )
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
        except Exception as e:
            logger.error(f"Failed to subscribe to topic: {str(e)}")
            return {"success_count": 0, "failure_count": len(tokens)}
    
    def unsubscribe_from_topic(
        self,
        tokens: List[str],
        topic: str
    ) -> Dict[str, Any]:
        """
        Unsubscribe devices from a topic
        
        Args:
            tokens: List of device tokens
            topic: Topic name
            
        Returns:
            Response with success/failure counts
        """
        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            logger.info(
                f"Topic unsubscription: {response.success_count} successful, "
                f"{response.failure_count} failed"
            )
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
        except Exception as e:
            logger.error(f"Failed to unsubscribe from topic: {str(e)}")
            return {"success_count": 0, "failure_count": len(tokens)}


# Singleton instance
firebase_integration = FirebaseIntegration()
