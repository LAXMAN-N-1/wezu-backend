"""
Enhanced Notification Endpoints
Additional notification operations including read/unread management and device tokens
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.models.notification import Notification
from app.db.session import get_session
from app.repositories.notification_repository import notification_repository
from pydantic import BaseModel

router = APIRouter()


class DeviceTokenRequest(BaseModel):
    token: str
    platform: str  # ios, android, web


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Mark a single notification as read"""
    notification = notification_repository.get(db, notification_id)
    
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification_repository.mark_as_read(db, notification_id)
    
    return {"message": "Notification marked as read"}


@router.patch("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Mark all notifications as read"""
    count = notification_repository.mark_all_as_read(db, current_user.id)
    
    return {
        "message": f"{count} notifications marked as read",
        "count": count
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Delete a single notification"""
    notification = notification_repository.get(db, notification_id)
    
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    
    return {"message": "Notification deleted"}


@router.delete("")
async def clear_all_notifications(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Clear all notifications"""
    notifications = notification_repository.get_user_notifications(db, current_user.id)
    
    for notification in notifications:
        db.delete(notification)
    
    db.commit()
    
    return {
        "message": f"{len(notifications)} notifications cleared",
        "count": len(notifications)
    }


@router.post("/device-token")
async def register_device_token(
    request: DeviceTokenRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Register device token for push notifications"""
    from app.models.device_token import DeviceToken
    from sqlmodel import select
    
    # Check if token already exists
    statement = select(DeviceToken).where(
        (DeviceToken.user_id == current_user.id) &
        (DeviceToken.token == request.token)
    )
    existing = db.exec(statement).first()
    
    if existing:
        existing.is_active = True
        db.add(existing)
    else:
        device_token = DeviceToken(
            user_id=current_user.id,
            token=request.token,
            platform=request.platform,
            is_active=True
        )
        db.add(device_token)
    
    db.commit()
    
    return {"message": "Device token registered successfully"}


@router.delete("/device-token")
async def unregister_device_token(
    request: DeviceTokenRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Unregister device token"""
    from app.models.device_token import DeviceToken
    from sqlmodel import select
    
    statement = select(DeviceToken).where(
        (DeviceToken.user_id == current_user.id) &
        (DeviceToken.token == request.token)
    )
    device_token = db.exec(statement).first()
    
    if device_token:
        device_token.is_active = False
        db.add(device_token)
        db.commit()
    
    return {"message": "Device token unregistered successfully"}
