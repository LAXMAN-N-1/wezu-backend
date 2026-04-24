from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()

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

# DECONFLICTED P0-B: PATCH /read-all removed.
# Canonical handler lives in app/api/v1/notifications_enhanced.py
# (supports app_scope filtering + include_global param).
# Removed 2026-04-06.

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


class InvoiceNotificationRequest(BaseModel):
    order_id: str
    type: str = "purchase_invoice"


@router.post("/invoice", response_model=dict)
async def send_invoice_notification(
    request: InvoiceNotificationRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Compatibility endpoint used by mobile clients after invoice generation.
    """
    try:
        NotificationService.send_notification(
            db,
            current_user,
            title="Invoice generated",
            message=f"Invoice for order {request.order_id} is ready.",
            type=request.type or "purchase_invoice",
            channel="push",
            app_scope="customer",
        )
    except Exception:
        # Best-effort endpoint: do not block caller if notification transport fails.
        return {"success": True, "message": "Invoice notification queued"}

    return {"success": True, "message": "Invoice notification sent"}

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

# DECONFLICTED P0-B: POST /device-token removed.
# Canonical handler lives in app/api/v1/notifications_enhanced.py
# (supports device_id, app_scope, cross-user token deactivation).
# Removed 2026-04-06.
