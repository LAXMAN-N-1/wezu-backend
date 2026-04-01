"""
Dealer Portal Settings — Profile update, notification preferences,
bank account, and notifications list.
"""
from typing import Any, Optional, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from pydantic import BaseModel, EmailStr
from datetime import datetime, UTC

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    business_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    
    # New Fields
    year_established: Optional[str] = None
    website_url: Optional[str] = None
    business_description: Optional[str] = None
    alternate_phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    support_email: Optional[EmailStr] = None
    support_phone: Optional[str] = None


class BankAccountRequest(BaseModel):
    account_number: str
    ifsc_code: str
    account_holder_name: str
    bank_name: str


class NotificationPrefsRequest(BaseModel):
    low_stock_email: bool = True
    low_stock_sms: bool = False
    low_stock_push: bool = True
    new_booking_email: bool = True
    new_booking_sms: bool = False
    new_booking_push: bool = True
    maintenance_email: bool = True
    maintenance_sms: bool = False
    maintenance_push: bool = True
    commission_email: bool = True
    commission_sms: bool = False
    commission_push: bool = True
    ticket_email: bool = True
    ticket_sms: bool = False
    ticket_push: bool = True


# ── Profile ──────────────────────────────────────────────

@router.get("/profile")
def get_profile(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get dealer profile."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")

    return {
        "id": dealer.id,
        "user_id": dealer.user_id,
        "business_name": dealer.business_name,
        "gst_number": dealer.gst_number,
        "pan_number": dealer.pan_number,
        
        "year_established": dealer.year_established,
        "website_url": dealer.website_url,
        "business_description": dealer.business_description,
        
        "contact_person": dealer.contact_person,
        "contact_email": dealer.contact_email,
        "contact_phone": dealer.contact_phone,
        "alternate_phone": dealer.alternate_phone,
        "whatsapp_number": dealer.whatsapp_number,
        "support_email": dealer.support_email,
        "support_phone": dealer.support_phone,
        
        "address_line1": dealer.address_line1,
        "city": dealer.city,
        "state": dealer.state,
        "pincode": dealer.pincode,
        
        "bank_details": dealer.bank_details,
        "is_active": dealer.is_active,
        "created_at": str(dealer.created_at),
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone_number,
        "profile_picture": current_user.profile_picture,
    }


@router.patch("/profile")
def update_profile(
    data: UpdateProfileRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update dealer profile fields."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")

    update_data = data.dict(exclude_unset=True, exclude_none=True)
    for key, value in update_data.items():
        setattr(dealer, key, value)

    db.add(dealer)
    db.commit()
    db.refresh(dealer)

    return {"message": "Profile updated", "id": dealer.id}


# ── Bank Account ─────────────────────────────────────────

@router.post("/bank-account")
def update_bank_account(
    data: BankAccountRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Add/update bank account for commission settlements."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")

    dealer.bank_details = {
        "account_number": data.account_number,
        "ifsc_code": data.ifsc_code,
        "account_holder_name": data.account_holder_name,
        "bank_name": data.bank_name,
        "verified": False,
        "updated_at": str(datetime.now(UTC)),
    }
    db.add(dealer)
    db.commit()

    return {"message": "Bank account updated", "verified": False}


@router.get("/bank-account")
def get_bank_account(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current bank account details."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")

    return {"bank_details": dealer.bank_details or {}}


# ── Notification Preferences ─────────────────────────────

@router.get("/notification-preferences")
def get_notification_preferences(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get notification toggle preferences."""
    prefs = db.exec(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    ).first()

    if not prefs:
        return {
            "notifications_enabled": True,
            "push_enabled": True,
            "email_enabled": True,
            "sms_enabled": False,
        }

    return {
        "notifications_enabled": prefs.notifications_enabled,
        "push_enabled": prefs.push_enabled,
        "email_enabled": prefs.email_enabled,
        "sms_enabled": prefs.sms_enabled,
        "battery_alerts_push": prefs.battery_alerts_push,
        "battery_alerts_email": prefs.battery_alerts_email,
        "rental_reminders_push": prefs.rental_reminders_push,
        "rental_reminders_email": prefs.rental_reminders_email,
        "payment_push": prefs.payment_push,
        "payment_email": prefs.payment_email,
        "maintenance_push": prefs.maintenance_push,
        "maintenance_email": prefs.maintenance_email,
    }


@router.put("/notification-preferences")
def update_notification_preferences(
    data: dict,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update notification preferences."""
    prefs = db.exec(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    ).first()

    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    for key, value in data.items():
        if hasattr(prefs, key):
            setattr(prefs, key, value)

    prefs.updated_at = datetime.now(UTC)
    db.add(prefs)
    db.commit()

    return {"message": "Notification preferences updated"}


# ── Notifications List ───────────────────────────────────

@router.get("/notifications")
def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List dealer notifications."""
    query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        query = query.where(Notification.is_read == False)

    query = query.order_by(Notification.created_at.desc())

    total = db.exec(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id
        )
    ).one() or 0

    unread_count = db.exec(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    ).one() or 0

    notifications = db.exec(query.offset((page - 1) * limit).limit(limit)).all()

    return {
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "is_read": n.is_read,
                "created_at": str(n.created_at),
            }
            for n in notifications
        ],
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit,
    }


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Mark a notification as read."""
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.add(notification)
    db.commit()

    return {"message": "Notification marked as read"}


@router.patch("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Mark all notifications as read."""
    notifications = db.exec(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    ).all()

    for n in notifications:
        n.is_read = True
        db.add(n)

    db.commit()


    return {"message": f"Marked {len(notifications)} notifications as read"}


# ── Global Settings & Defaults ───────────────────────────

@router.get("/station-defaults")
def get_station_defaults(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get global station defaults for the dealer."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    return {"station_defaults": dealer.global_station_defaults or {}}


@router.patch("/station-defaults")
def update_station_defaults(
    data: Dict[str, Any],
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update global station defaults."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    
    current_defaults = dealer.global_station_defaults or {}
    current_defaults.update(data)
    dealer.global_station_defaults = current_defaults
    
    db.add(dealer)
    db.commit()
    return {"message": "Station defaults updated"}


@router.get("/inventory-rules")
def get_inventory_rules(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get global inventory rule thresholds."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    return {"inventory_rules": dealer.global_inventory_rules or {}}


@router.patch("/inventory-rules")
def update_inventory_rules(
    data: Dict[str, Any],
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update global inventory rules."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    
    current_rules = dealer.global_inventory_rules or {}
    current_rules.update(data)
    dealer.global_inventory_rules = current_rules
    
    db.add(dealer)
    db.commit()
    return {"message": "Inventory rules updated"}


@router.get("/holiday-calendar")
def get_holiday_calendar(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get dealer's holiday calendar."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    return {"holiday_calendar": dealer.holiday_calendar or []}


@router.patch("/holiday-calendar")
def update_holiday_calendar(
    data: List[Dict[str, Any]],
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update holiday calendar (full replacement)."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    
    dealer.holiday_calendar = data
    db.add(dealer)
    db.commit()
    return {"message": "Holiday calendar updated"}
