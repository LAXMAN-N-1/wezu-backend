import base64
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    SendEmailRequest,
    SendEmailResponse,
)
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService, EmailAttachment

router = APIRouter()


# ---------------------------------------------------------------------------
# Email (Reports / Maps via Email with Attachments)
# ---------------------------------------------------------------------------

@router.post("/send-email", response_model=SendEmailResponse, summary="Send email with attachments")
async def send_email(
    request: SendEmailRequest,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Send an email (with optional attachments) to one or more recipients.

    Useful for sharing reports, maps, and generated documents.

    - **to**: List of recipient email addresses.
    - **subject**: Email subject line.
    - **body_html**: HTML body content.
    - **cc / bcc**: Optional CC / BCC recipients.
    - **attachments**: Optional list of files encoded as base64.
      Each attachment needs a `filename`, `content_base64`, and optionally a `mime_type`.

    Returns success status and a count of attachments sent.
    """
    # Decode base64 attachments from request into EmailAttachment objects
    decoded_attachments: list[EmailAttachment] = []
    for att in request.attachments:
        try:
            raw_bytes = base64.b64decode(att.content_base64)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid base64 content for attachment '{att.filename}'"
            )
        decoded_attachments.append(
            EmailAttachment(
                filename=att.filename,
                content=raw_bytes,
                mime_type=att.mime_type,
            )
        )

    success = EmailService.send_email_with_attachments(
        to_emails=[str(addr) for addr in request.to],
        subject=request.subject,
        html_content=request.body_html,
        attachments=decoded_attachments,
        cc=[str(addr) for addr in request.cc],
        bcc=[str(addr) for addr in request.bcc],
    )

    if not success:
        raise HTTPException(
            status_code=502,
            detail="Failed to send email. Please check your SendGrid configuration."
        )

    return SendEmailResponse(
        success=True,
        message="Email sent successfully",
        recipients=[str(addr) for addr in request.to],
        attachment_count=len(decoded_attachments),
    )


@router.get("/my", response_model=List[NotificationResponse])

async def read_notifications(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Customer: fetch in-app notification inbox"""
    return NotificationService.get_user_notifications(db, current_user.id)

@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Mark a single notification as read"""
    NotificationService.mark_read(db, notification_id, current_user.id)
    return {"message": "Notification marked as read"}

@router.patch("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Mark all notifications as read"""
    count = NotificationService.mark_all_read(db, current_user.id)
    return {
        "message": f"{count} notifications marked as read",
        "count": count
    }

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Delete a single notification"""
    from app.models.notification import Notification
    notif = db.get(Notification, notification_id)
    if notif and notif.user_id == current_user.id:
        db.delete(notif)
        db.commit()
    return {"message": "Notification deleted"}

@router.delete("/")
async def clear_all_notifications(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Clear all notifications"""
    count = NotificationService.clear_all_notifications(db, current_user.id)
    return {
        "message": f"{count} notifications cleared",
        "count": count
    }

# --- New Gaps Endpoints ---
from app.schemas.notification import AdminNotificationSendRequest, UnreadCountResponse

@router.post("/send", response_model=dict)
async def admin_send_notification(
    request: AdminNotificationSendRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Admin: send push/SMS/email notification to a specific user"""
    user = db.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    NotificationService.send_notification(
        db, user, request.title, request.message, request.type, request.channel
    )
    return {"message": "Notification sent successfully"}

@router.post("/admin/bulk", response_model=dict)
async def admin_bulk_notification(
    request: AdminNotificationSendRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Admin: bulk notification to filtered user segments"""
    count = NotificationService.send_bulk_notification(
        db, request.segment or "all", request.title, request.message, request.type, request.channel
    )
    return {"message": f"Broadcasted to {count} users"}

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_my_unread_count(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get badge count for unread notifications"""
    count = NotificationService.get_unread_count(db, current_user.id)
    return {"unread_count": count}

# Standardizing PUT methods as requested for mark-as-read
@router.put("/{notification_id}/read")
async def put_mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Mark a specific notification as read (PUT)"""
    NotificationService.mark_read(db, notification_id, current_user.id)
    return {"message": "Notification marked as read"}

@router.put("/read-all")
async def put_mark_all_read(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Mark all notifications as read (PUT)"""
    count = NotificationService.mark_all_read(db, current_user.id)
    return {"message": f"{count} notifications marked as read", "count": count}

from pydantic import BaseModel
class DeviceTokenRequest(BaseModel):
    token: str
    platform: str  # ios, android, web

@router.post("/device-token")
async def register_device_token(
    request: DeviceTokenRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Register device token for push notifications"""
    from app.models.device import Device
    from sqlmodel import select
    
    # Check if token already exists
    statement = select(Device).where(
        (Device.user_id == current_user.id) &
        (Device.fcm_token == request.token)
    )
    existing = db.exec(statement).first()
    
    if existing:
        existing.is_active = True
        db.add(existing)
    else:
        device = Device(
            user_id=current_user.id,
            fcm_token=request.token,
            device_type=request.platform,
            is_active=True
        )
        db.add(device)
    
    db.commit()
    return {"message": "Device token registered successfully"}
