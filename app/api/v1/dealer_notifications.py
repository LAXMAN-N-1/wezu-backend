from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.notification import Notification
from app.models.dealer_notification_pref import DealerNotificationPreference
from app.schemas.dealer_notification import (
    DealerNotificationPreferenceResponse,
    DealerNotificationPreferenceUpdate,
    QuietHoursSchema
)
from app.schemas.notification import NotificationResponse, UnreadCountResponse

router = APIRouter()

def get_current_dealer(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> DealerProfile:
    """Dependency to ensure user is a dealer and fetch their profile"""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Dealer profile not found")
    return dealer

@router.get("/preferences", response_model=DealerNotificationPreferenceResponse)
async def get_dealer_preferences(
    dealer: DealerProfile = Depends(get_current_dealer),
    db: Session = Depends(deps.get_db)
):
    """Get current dealer notification preferences or create default if missing."""
    pref = db.exec(select(DealerNotificationPreference).where(DealerNotificationPreference.dealer_id == dealer.id)).first()
    if not pref:
        # Create default preferences for the dealer
        pref = DealerNotificationPreference(dealer_id=dealer.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
        
    return pref

@router.put("/preferences", response_model=DealerNotificationPreferenceResponse)
async def update_dealer_preferences(
    prefs_in: DealerNotificationPreferenceUpdate,
    dealer: DealerProfile = Depends(get_current_dealer),
    db: Session = Depends(deps.get_db)
):
    """Update dealer notification preferences. Supports partial updates."""
    pref = db.exec(select(DealerNotificationPreference).where(DealerNotificationPreference.dealer_id == dealer.id)).first()
    if not pref:
        pref = DealerNotificationPreference(dealer_id=dealer.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
        
    update_data = prefs_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        # quiet_hours is handled as a dict
        if key == "quiet_hours" and value is not None:
            pref.quiet_hours_enabled = True
            pref.quiet_hours = value
        else:
            setattr(pref, key, value)
            
    pref.updated_at = datetime.utcnow()
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref

@router.get("", response_model=List[NotificationResponse])
async def list_dealer_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user),
    dealer: DealerProfile = Depends(get_current_dealer),
    db: Session = Depends(deps.get_db)
):
    """List all notifications targeted specifically at the dealer."""
    # Dealer notifications are essentially notifications sent to the User account.
    # Notifications meant for dealer usually have type='dealer_alert' or just general user notifications
    return db.exec(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .offset(skip).limit(limit)
    ).all()

@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    dealer: DealerProfile = Depends(get_current_dealer),
    db: Session = Depends(deps.get_db)
):
    """Mark a specific notification as read."""
    notif = db.get(Notification, notification_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notif.is_read = True
    db.add(notif)
    db.commit()
    return {"message": "Notification marked as read"}

@router.patch("/read-all")
async def mark_all_read(
    current_user: User = Depends(deps.get_current_user),
    dealer: DealerProfile = Depends(get_current_dealer),
    db: Session = Depends(deps.get_db)
):
    """Mark all unread notifications as read."""
    unread = db.exec(
        select(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    ).all()
    
    count = len(unread)
    for notif in unread:
        notif.is_read = True
        db.add(notif)
    db.commit()
    return {"message": f"{count} notifications marked as read", "count": count}

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(deps.get_current_user),
    dealer: DealerProfile = Depends(get_current_dealer),
    db: Session = Depends(deps.get_db)
):
    """Get count of unread notifications for badge display."""
    from sqlmodel import func
    count = db.exec(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    ).first() or 0
    return {"unread_count": count}
