import random
import string
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select
from app.models.otp import OTP
from app.core.config import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger("wezu_auth")


def _mask_target(value: str) -> str:
    if not value:
        return "***"
    if "@" in value:
        local, _, domain = value.partition("@")
        if len(local) <= 2:
            return f"{'*' * len(local)}@{domain}"
        return f"{local[0]}***{local[-1]}@{domain}"
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"


class OTPService:
    @staticmethod
    def generate_otp(target: str, purpose: str = "registration", length: int = 6) -> str:
        code = ''.join(random.choices(string.digits, k=length))
        return code

    @staticmethod
    def create_otp_record(
        db: Session,
        target: str,
        code: str,
        purpose: str = "registration",
        validity_minutes: int = 15,
        *,
        auto_commit: bool = True,
    ) -> OTP:
        # Rate Limiting Logic
        # 1. Count OTPs in the last 30 minutes
        window_start = datetime.utcnow() - timedelta(minutes=30)
        statement = select(OTP).where(
            OTP.target == target, 
            OTP.purpose == purpose, 
            OTP.created_at > window_start
        ).order_by(OTP.created_at.desc())
        
        recent_otps = db.exec(statement).all()
        count = len(recent_otps)
        
        # 2. Hard Limit: Max 3 OTPs per 30 mins
        if count >= 3:
             from fastapi import HTTPException
             raise HTTPException(
                 status_code=429, 
                 detail="Maximum OTP limit reached. Please try again after 30 minutes."
            )
            
        # 3. Progressive Delays
        if count > 0:
            last_otp_time = recent_otps[0].created_at
            time_since_last = datetime.utcnow() - last_otp_time
            
            # After 1st OTP (attempting 2nd): Wait 1 minute
            if count == 1 and time_since_last < timedelta(minutes=1):
                 from fastapi import HTTPException
                 wait_seconds = 60 - int(time_since_last.total_seconds())
                 raise HTTPException(
                     status_code=429, 
                     detail=f"Please wait {wait_seconds} seconds before requesting a new OTP."
                )
            
            # After 2nd OTP (attempting 3rd): Wait 5 minutes
            if count == 2 and time_since_last < timedelta(minutes=5):
                 from fastapi import HTTPException
                 wait_minutes = 5 - int(time_since_last.total_seconds() / 60)
                 raise HTTPException(
                     status_code=429, 
                     detail=f"Please wait {wait_minutes} minutes before requesting a new OTP."
                )

        # Deactivate previous OTPs for the same target and purpose
        statement = select(OTP).where(OTP.target == target, OTP.purpose == purpose, OTP.is_active == True)
        old_otps = db.exec(statement).all()
        for old_otp in old_otps:
            old_otp.is_active = False # Mark as inactive instead of is_used
            db.add(old_otp)
        
        expires_at = datetime.utcnow() + timedelta(minutes=validity_minutes)
        otp_record = OTP(
            target=target,
            code=code,
            purpose=purpose,
            expires_at=expires_at,
            is_active=True
        )
        db.add(otp_record)
        if auto_commit:
            db.commit()
            db.refresh(otp_record)
        else:
            db.flush()
        return otp_record

    @staticmethod
    async def send_email_otp(email: str, code: str):
        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=email,
            subject='Your WEZU Verification Code',
            html_content=f'<strong>Your verification code is: {code}</strong><br>It expires in 15 minutes.'
        )
        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            return response.status_code
        except Exception:
            logger.exception("Error sending OTP email to %s", _mask_target(email))
            return None

    @staticmethod
    async def send_sms_otp(phone: str, code: str):
        from app.integrations.twilio import twilio_integration
        
        # Ensure phone is in E.164 format for Twilio (starts with +)
        # Smart formatting for Indian numbers: if 10 digits, prefix +91
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) == 10 and not phone.startswith("+"):
            formatted_phone = f"+91{clean_phone}"
        else:
            formatted_phone = phone if phone.startswith("+") else f"+{phone}"
        
        if settings.SMS_PROVIDER == "twilio" and settings.TWILIO_ACCOUNT_SID:
            # If Verify Service SID is present, use Twilio Verify API (Recommended)
            if getattr(settings, "TWILIO_VERIFY_SERVICE_SID", None):
                result = twilio_integration.send_verification_code(formatted_phone)
                if result:
                    logger.info("OTP verification request sent via Twilio Verify to %s", _mask_target(formatted_phone))
                    return True
                else:
                    logger.error("Failed to send OTP via Twilio Verify to %s", _mask_target(formatted_phone))
            
            # Fallback to standard SMS API
            result = twilio_integration.send_otp(formatted_phone, code)
            if result:
                logger.info("OTP sent via basic Twilio SMS to %s", _mask_target(formatted_phone))
                return True
            else:
                logger.error("Failed to send OTP via basic Twilio SMS to %s. Check your credentials in .env.", _mask_target(formatted_phone))
                # We return True even if SMS fails in dev/debug so the user isn't blocked by provider issues
                return settings.ENVIRONMENT == "development" or settings.DEBUG
        
        # Placeholder for other providers
        if settings.ENVIRONMENT == "production" and not settings.DEBUG:
            logger.error("SMS provider is not configured for production")
            return False

        logger.info("DEBUG: [MOCK SMS] Sending OTP to %s", _mask_target(formatted_phone))
        return True

    @staticmethod
    def verify_otp(db: Session, target: str, code: str, purpose: str = "registration") -> bool:
        # Controlled test bypass for non-production testing only
        if settings.ALLOW_TEST_OTP_BYPASS and code == "123456":
            return True
             
        from app.integrations.twilio import twilio_integration
        
        # Ensure phone is in E.164 if it's a phone number
        formatted_target = target
        if "@" not in target:
            # Smart formatting for Indian numbers: if 10 digits, prefix +91
            clean_phone = "".join(filter(str.isdigit, target))
            if len(clean_phone) == 10 and not target.startswith("+"):
                formatted_target = f"+91{clean_phone}"
            else:
                formatted_target = target if target.startswith("+") else f"+{target}"
            
            # If Verify Service SID is present, check with Twilio Verify first
            if settings.SMS_PROVIDER == "twilio" and getattr(settings, "TWILIO_VERIFY_SERVICE_SID", None):
                if twilio_integration.verify_code(formatted_target, code):
                    logger.info("OTP verified via Twilio Verify for %s", _mask_target(formatted_target))
                    return True

        # Find the active OTP for this target in our database
        statement = select(OTP).where(
            OTP.target == target,
            OTP.purpose == purpose,
            OTP.is_active == True,
            OTP.is_used == False,
            OTP.expires_at > datetime.utcnow()
        )
        otp_record = db.exec(statement).first()
        
        if not otp_record:
            return False
            
        # Logging failed attempt if code doesn't match
        if otp_record.code != code:
            otp_record.attempts += 1
            if otp_record.attempts >= 5:
                # Lock the OTP after 5 tries per security requirement
                otp_record.is_active = False 
            db.add(otp_record)
            db.commit()
            return False
            
        # Success Case
        otp_record.is_used = True
        otp_record.is_active = False # Deactivate after use
        db.add(otp_record)
        db.commit()
        return True
