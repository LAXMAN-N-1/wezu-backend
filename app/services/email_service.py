import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _is_non_production() -> bool:
        environment = (settings.ENVIRONMENT or "").strip().lower()
        return settings.DEBUG or environment in {"development", "dev", "test", "local"}

    @staticmethod
    def send_email(to_email: str, subject: str, content: str) -> bool:
        if not to_email or "@" not in to_email:
            logger.warning("Email not sent: invalid recipient '%s'", to_email)
            return False

        if not (subject or "").strip() or not (content or "").strip():
            logger.warning("Email not sent: empty subject/content")
            return False

        emails_enabled = bool(settings.EMAILS_ENABLED)
        has_sendgrid_key = bool(settings.SENDGRID_API_KEY)
        if not emails_enabled or not has_sendgrid_key:
            logger.info("MOCK EMAIL to %s: %s", to_email, subject)
            return EmailService._is_non_production()

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
        except Exception:
            logger.exception("SendGrid package is unavailable")
            return EmailService._is_non_production()

        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL or "noreply@wezu.com",
            to_emails=to_email,
            subject=subject,
            html_content=content,
        )
        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            return response.status_code == 202
        except Exception:
            logger.exception("Error sending email to %s", to_email)
            return False

    @staticmethod
    def send_otp(to_email: str, otp: str) -> bool:
        subject = "Your Wezu Verification Code"
        content = f"<h3>Your OTP is: <b>{otp}</b></h3><p>Valid for 10 minutes.</p>"
        return EmailService.send_email(to_email, subject, content)
