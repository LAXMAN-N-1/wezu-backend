from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, content: str):
        if not settings.SENDGRID_API_KEY:
             logger.info(f"MOCK EMAIL to {to_email}: {subject}")
             return True

        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL or "noreply@wezu.com",
            to_emails=to_email,
            subject=subject,
            html_content=content
        )
        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            return response.status_code == 202
        except Exception as e:
            logger.warning(f"Error sending email: {e}")
            return False

    @staticmethod
    def send_otp(to_email: str, otp: str):
        subject = "Your Wezu Verification Code"
        content = f"<h3>Your OTP is: <b>{otp}</b></h3><p>Valid for 10 minutes.</p>"
        return EmailService.send_email(to_email, subject, content)
