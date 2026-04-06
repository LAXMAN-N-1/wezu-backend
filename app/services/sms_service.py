import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSService:
    @staticmethod
    def _is_non_production() -> bool:
        environment = (settings.ENVIRONMENT or "").strip().lower()
        return settings.DEBUG or environment in {"development", "dev", "test", "local"}

    @staticmethod
    def _normalize_phone(phone: str) -> Optional[str]:
        if not phone:
            return None

        digits = "".join(ch for ch in phone if ch.isdigit())
        if not digits:
            return None

        if phone.startswith("+"):
            return f"+{digits}"

        if len(digits) == 10:
            # Current deployments are India-first; normalize local 10-digit numbers to +91.
            return f"+91{digits}"

        if len(digits) >= 11:
            return f"+{digits}"

        return None

    @staticmethod
    def send_sms(phone: str, message: str) -> bool:
        normalized_phone = SMSService._normalize_phone(phone)
        if not normalized_phone:
            logger.warning("SMS not sent: invalid phone number '%s'", phone)
            return False

        cleaned_message = (message or "").strip()
        if not cleaned_message:
            logger.warning("SMS not sent: empty message")
            return False

        provider = (settings.SMS_PROVIDER or "").strip().lower()
        if (
            provider == "twilio"
            and settings.TWILIO_ACCOUNT_SID
            and settings.TWILIO_AUTH_TOKEN
            and settings.TWILIO_PHONE_NUMBER
        ):
            try:
                from app.integrations.twilio import twilio_integration

                result = twilio_integration.send_sms(normalized_phone, cleaned_message)
                return bool(result)
            except Exception:
                logger.exception("Twilio SMS send failed for %s", normalized_phone)
                if SMSService._is_non_production():
                    logger.info("Using mock SMS success fallback in non-production")
                    return True
                return False

        logger.info("MOCK SMS to %s: %s", normalized_phone, cleaned_message)
        return SMSService._is_non_production()

    @staticmethod
    def send_otp(phone: str, otp: str) -> bool:
        message = f"Your Wezu verification code is {otp}. Do not share this with anyone."
        return SMSService.send_sms(phone, message)
