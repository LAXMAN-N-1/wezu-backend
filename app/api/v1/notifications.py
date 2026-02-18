from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
async def read_notifications(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
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
