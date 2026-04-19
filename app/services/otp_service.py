from __future__ import annotations
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


def _normalize_test_target(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "@" in raw:
        return raw.lower()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits


def _is_test_bypass_target(target: str) -> bool:
    configured_targets = getattr(settings, "TEST_OTP_BYPASS_TARGETS", []) or []
    normalized_target = _normalize_test_target(target)
    if not normalized_target:
        return False
    normalized_allowed = {
        _normalize_test_target(item)
        for item in configured_targets
        if _normalize_test_target(item)
    }
    # Backward-compatible behavior:
    # if bypass is enabled and target list is empty, allow all targets.
    if not normalized_allowed:
        return True
    return normalized_target in normalized_allowed


def _configured_test_bypass_code() -> str:
    return str(getattr(settings, "TEST_OTP_BYPASS_CODE", "") or "").strip()


def _configured_seeded_login_otp(target: str, purpose: str) -> str:
    if purpose != "login":
        return ""
    code = _configured_test_bypass_code()
    if (
        settings.ALLOW_TEST_OTP_BYPASS
        and code
        and _is_test_bypass_target(target)
    ):
        return code
    return ""


class OTPService:
    @staticmethod
    def generate_otp(target: str, purpose: str = "registration", length: int = 6) -> str:
        fixed_code = _configured_seeded_login_otp(target, purpose)
        if fixed_code:
            return fixed_code
        return ''.join(random.choices(string.digits, k=length))

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
        fixed_code = _configured_seeded_login_otp(target, purpose)
        if fixed_code and code == fixed_code:
            expires_at = datetime.utcnow() + timedelta(minutes=validity_minutes)
            statement = select(OTP).where(
                OTP.target == target,
                OTP.purpose == purpose,
                OTP.is_active == True,
            ).order_by(OTP.created_at.desc())
            active_otps = db.exec(statement).all()

            primary = active_otps[0] if active_otps else None
            for old_otp in active_otps:
                if primary is None or old_otp.id != primary.id:
                    old_otp.is_active = False
                    db.add(old_otp)

            if primary is None:
                primary = OTP(
                    target=target,
                    code=code,
                    purpose=purpose,
                    expires_at=expires_at,
                    is_active=True,
                    is_used=False,
                    attempts=0,
                )
            else:
                primary.code = code
                primary.expires_at = expires_at
                primary.is_active = True
                primary.is_used = False
                primary.attempts = 0
            db.add(primary)
            if auto_commit:
                db.commit()
                db.refresh(primary)
            else:
                db.flush()
            return primary

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

        bypass_code = _configured_test_bypass_code()
        # Controlled bypass for local/dev flows:
        # when test bypass is explicitly configured for this target we skip SMS.
        if (
            settings.ALLOW_TEST_OTP_BYPASS
            and bypass_code
            and _is_test_bypass_target(phone)
        ):
            logger.info(
                "DEBUG: [OTP BYPASS] Skipping SMS send for %s",
                _mask_target(phone),
            )
            return True
        
        # Ensure phone is in E.164 format for Twilio (starts with +)
        # Smart formatting for Indian numbers: if 10 digits, prefix +91
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) == 10 and not phone.startswith("+"):
            formatted_phone = f"+91{clean_phone}"
        else:
            formatted_phone = phone if phone.startswith("+") else f"+{phone}"

        sid = (settings.TWILIO_ACCOUNT_SID or "").strip()
        token = (settings.TWILIO_AUTH_TOKEN or "").strip()
        normalized_sid = sid.lower()
        normalized_token = token.lower()
        uses_placeholder_twilio = (
            "xxxx" in normalized_sid
            or "xxxx" in normalized_token
            or "your-" in normalized_sid
            or "your-" in normalized_token
            or sid == "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            or token == "your-twilio-auth-token"
        )
        
        if (
            settings.SMS_PROVIDER == "twilio"
            and sid
            and token
            and not uses_placeholder_twilio
        ):
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
        
        if settings.SMS_PROVIDER == "twilio" and uses_placeholder_twilio:
            if settings.ENVIRONMENT == "development" or settings.DEBUG:
                logger.info(
                    "DEBUG: [MOCK SMS] Twilio credentials are placeholders; OTP for %s is %s",
                    _mask_target(formatted_phone),
                    code,
                )
                return True
            logger.error("Twilio credentials are placeholders in production")
            return False

        # Placeholder for other providers
        if settings.ENVIRONMENT == "production" and not settings.DEBUG:
            logger.error("SMS provider is not configured for production")
            return False

        logger.info(
            "DEBUG: [MOCK SMS] Sending OTP to %s with code %s",
            _mask_target(formatted_phone),
            code,
        )
        return True

    @staticmethod
    def verify_otp(db: Session, target: str, code: str, purpose: str = "registration") -> bool:
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
