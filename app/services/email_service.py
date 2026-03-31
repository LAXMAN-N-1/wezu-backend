import base64
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName,
    FileType, Disposition, To, Cc, Bcc
)
from app.core.config import settings


class EmailAttachment:
    """Represents a single email attachment."""
    def __init__(self, filename: str, content: bytes, mime_type: str = "application/octet-stream"):
        self.filename = filename
        self.content = content
        self.mime_type = mime_type


class EmailService:

    @staticmethod
    def send_email(to_email: str, subject: str, content: str) -> bool:
        """Send a plain HTML email to a single recipient (no attachments)."""
        if not settings.SENDGRID_API_KEY:
            print(f"MOCK EMAIL to {to_email}: {subject}\n{content}")
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
            print(f"Error sending email: {e}")
            return False

    @staticmethod
    def send_otp(to_email: str, otp: str) -> bool:
        """Send an OTP verification email."""
        subject = "Your Wezu Verification Code"
        content = f"<h3>Your OTP is: <b>{otp}</b></h3><p>Valid for 10 minutes.</p>"
        return EmailService.send_email(to_email, subject, content)

    @staticmethod
    def send_email_with_attachments(
        to_emails: list[str],
        subject: str,
        html_content: str,
        attachments: Optional[list[EmailAttachment]] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> bool:
        """
        Send an HTML email to one or more recipients with optional file attachments.

        Args:
            to_emails:    List of recipient email addresses.
            subject:      Email subject line.
            html_content: HTML body of the email.
            attachments:  Optional list of EmailAttachment objects.
            cc:           Optional list of CC recipients.
            bcc:          Optional list of BCC recipients.

        Returns:
            True if email was sent (or mocked) successfully, False otherwise.
        """
        attachments = attachments or []
        cc = cc or []
        bcc = bcc or []

        if not settings.SENDGRID_API_KEY:
            print(
                f"MOCK EMAIL (with attachments)\n"
                f"  To:          {to_emails}\n"
                f"  Subject:     {subject}\n"
                f"  CC:          {cc}\n"
                f"  BCC:         {bcc}\n"
                f"  Attachments: {[a.filename for a in attachments]}"
            )
            return True

        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL or "noreply@wezu.com",
            subject=subject,
            html_content=html_content,
        )

        # Recipients
        message.to = [To(email=addr) for addr in to_emails]
        if cc:
            message.cc = [Cc(email=addr) for addr in cc]
        if bcc:
            message.bcc = [Bcc(email=addr) for addr in bcc]

        # Attachments
        for att in attachments:
            encoded = base64.b64encode(att.content).decode()
            sg_attachment = Attachment(
                file_content=FileContent(encoded),
                file_name=FileName(att.filename),
                file_type=FileType(att.mime_type),
                disposition=Disposition("attachment"),
            )
            message.add_attachment(sg_attachment)

        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            return response.status_code == 202
        except Exception as e:
            print(f"Error sending email with attachments: {e}")
            return False
