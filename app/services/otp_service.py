import random
import string
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select, col, desc
from app.models.otp import OTP
from app.core.config import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class OTPService:
    @staticmethod
    def generate_otp(target: str, purpose: str = "registration", length: int = 6) -> str:
        """Create an OTP. Only allow the static test code in non-production."""
        if (settings.ENVIRONMENT != "production") and settings.DEBUG:
            return "964056"
        code = ''.join(random.choices(string.digits, k=length))
        return code

    @staticmethod
    def create_otp_record(db: Session, target: str, code: str, purpose: str = "registration", validity_minutes: int = 15) -> OTP:
        # Rate Limiting Logic
        # 1. Count OTPs in the last 30 minutes
        window_start = datetime.utcnow() - timedelta(minutes=30)
        statement = select(OTP).where(
            col(OTP.target) == target, 
            col(OTP.purpose) == purpose, 
            col(OTP.created_at) > window_start
        ).order_by(desc(OTP.created_at))
        
        recent_otps = list(db.exec(statement).all())
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
        statement = select(OTP).where(col(OTP.target) == target, col(OTP.purpose) == purpose, col(OTP.is_active) == True)
        old_otps = list(db.exec(statement).all())
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
        db.commit()
        db.refresh(otp_record)
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
        except Exception as e:
            print(f"Error sending email: {e}")
            return None

    @staticmethod
    async def send_sms_otp(phone: str, code: str):
        from app.integrations.twilio import twilio_integration
        import logging
        logger = logging.getLogger("wezu_auth")
        
        # Ensure phone is in E.164 format for Twilio (starts with +)
        # Smart formatting for Indian numbers: if 10 digits, prefix +91
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) == 10 and not phone.startswith("+"):
            formatted_phone = f"+91{clean_phone}"
        else:
            formatted_phone = phone if phone.startswith("+") else f"+{phone}"
        
        # Always log to console for development visibility
        logger.info(f"OTP_CODE_FOR_{formatted_phone}: {code}")

        if settings.SMS_PROVIDER == "twilio" and settings.TWILIO_ACCOUNT_SID:
            # If Verify Service SID is present, use Twilio Verify API (Recommended)
            if getattr(settings, "TWILIO_VERIFY_SERVICE_SID", None):
                result = twilio_integration.send_verification_code(formatted_phone)
                if result:
                    logger.info(f"INFO: OTP verification request sent via Twilio Verify to {formatted_phone}")
                    return True
                else:
                    logger.error(f"ERROR: Failed to send OTP via Twilio Verify to {formatted_phone}")
            
            # Fallback to standard SMS API
            result = twilio_integration.send_otp(formatted_phone, code)
            if result:
                logger.info(f"INFO: OTP sent via basic Twilio SMS to {formatted_phone}")
                return True
            else:
                logger.error(f"ERROR: Failed to send OTP via basic Twilio SMS to {formatted_phone}. Check your credentials in .env.")
                # We return True even if SMS fails in dev/debug so the user isn't blocked by provider issues
                return settings.ENVIRONMENT == "development" or settings.DEBUG
        
        # Placeholder for other providers
        logger.info(f"DEBUG: [MOCK SMS] Sending SMS to {formatted_phone} with code {code}")
        return True

    @staticmethod
    def verify_otp(db: Session, target: str, code: str, purpose: str = "registration") -> bool:
        # Mock OTP Bypass for Testing (only in non-prod)
        if (settings.ENVIRONMENT != "production") and settings.DEBUG and code == "964056":
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
                    print(f"INFO: OTP verified via Twilio Verify for {formatted_target}")
                    return True

        # Find the active OTP for this target in our database
        statement = select(OTP).where(
            col(OTP.target) == target,
            col(OTP.purpose) == purpose,
            col(OTP.is_active) == True,
            col(OTP.is_used) == False,
            col(OTP.expires_at) > datetime.utcnow()
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
