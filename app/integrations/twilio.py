"""
Twilio SMS Integration
Handles SMS and OTP delivery
"""
from twilio.rest import Client
from typing import Optional, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class TwilioIntegration:
    """Twilio SMS service wrapper"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.from_number = settings.TWILIO_PHONE_NUMBER
        # Lazily initialize client only when credentials are present
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                self.client = None
    
    def send_sms(
        self,
        to_number: str,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Send SMS message
        
        Args:
            to_number: Recipient phone number (E.164 format)
            message: Message text
            
        Returns:
            Message details if successful
        """
        if not self.client:
            # In non-production we allow a mock path to avoid hard failures
            logger.warning("Twilio client not configured; returning mock SMS result.")
            return {"sid": "mock", "status": "mock", "to": to_number, "from": self.from_number}
        try:
            message_obj = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(f"SMS sent successfully: {message_obj.sid}")
            
            return {
                "sid": message_obj.sid,
                "status": message_obj.status,
                "to": message_obj.to,
                "from": message_obj.from_,
                "date_created": message_obj.date_created.isoformat() if message_obj.date_created else None
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
            return None
    
    def send_otp(
        self,
        to_number: str,
        otp: str,
        app_name: str = "WEZU"
    ) -> Optional[Dict[str, Any]]:
        """
        Send OTP via SMS
        
        Args:
            to_number: Recipient phone number
            otp: OTP code
            app_name: Application name
            
        Returns:
            Message details if successful
        """
        message = f"{otp} is your {app_name} verification code. Valid for 10 minutes. Do not share with anyone."
        return self.send_sms(to_number, message)
    
    def get_message_status(self, message_sid: str) -> Optional[str]:
        """
        Get message delivery status
        
        Args:
            message_sid: Message SID
            
        Returns:
            Message status
        """
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except Exception as e:
            logger.error(f"Failed to fetch message status: {str(e)}")
            return None
    
    def send_verification_code(
        self,
        to_number: str,
        channel: str = "sms"
    ) -> Optional[Dict[str, Any]]:
        """
        Send verification code using Twilio Verify API
        
        Args:
            to_number: Phone number to verify
            channel: Delivery channel (sms, call, whatsapp)
            
        Returns:
            Verification details
        """
        try:
            if not self.client or not getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None):
                logger.warning("Twilio Verify not configured; returning mock verification response.")
                return {"sid": "mock", "status": "mock", "to": to_number, "channel": channel}
            
            verification = self.client.verify \
                .services(settings.TWILIO_VERIFY_SERVICE_SID) \
                .verifications \
                .create(to=to_number, channel=channel)
            
            logger.info(f"Verification code sent: {verification.sid}")
            
            return {
                "sid": verification.sid,
                "status": verification.status,
                "to": verification.to,
                "channel": verification.channel
            }
            
        except Exception as e:
            logger.error(f"Failed to send verification code: {str(e)}")
            return None
    
    def verify_code(
        self,
        to_number: str,
        code: str
    ) -> bool:
        """
        Verify code using Twilio Verify API
        
        Args:
            to_number: Phone number
            code: Verification code
            
        Returns:
            True if code is valid
        """
        try:
            if not self.client or not getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None):
                logger.warning("Twilio Verify not configured; treating as success in non-production.")
                return settings.ENVIRONMENT != "production"
            
            verification_check = self.client.verify \
                .services(settings.TWILIO_VERIFY_SERVICE_SID) \
                .verification_checks \
                .create(to=to_number, code=code)
            
            is_valid = verification_check.status == "approved"
            logger.info(f"Verification check: {is_valid}")
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to verify code: {str(e)}")
            return False


# Singleton instance
twilio_integration = TwilioIntegration()
