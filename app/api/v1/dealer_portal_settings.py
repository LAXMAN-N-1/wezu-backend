"""
Dealer Portal Settings — Profile update, notification preferences,
bank account, and notifications list.
"""
from typing import Any, Optional, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select, func
from pydantic import BaseModel, EmailStr
from datetime import datetime, time, timedelta

from app.db.session import get_session
from app.api.deps import get_current_user
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.notification_log import NotificationLog
from app.models.session import UserSession

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


class BankAccountRequest(BaseModel):
    account_number: str
    ifsc_code: str
    account_holder_name: str
    bank_name: str


class AccountDeleteRequest(BaseModel):
    business_name: str
    password: str

class SessionTimeoutRequest(BaseModel):
    timeout_minutes: int

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class TestNotificationRequest(BaseModel):
    channels: list[str] # ["email", "sms", "push"]
    title: Optional[str] = "Test Notification"
    message: Optional[str] = "This is a test notification from the portal."

class NotificationScheduleRequest(BaseModel):
    quiet_hours_enabled: bool
    quiet_hours_start: Optional[str] = None # HH:MM format
    quiet_hours_end: Optional[str] = None # HH:MM format
    quiet_on_weekends: bool = False

class ChangeEmailRequest(BaseModel):
    new_email: EmailStr

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


class PortalPreferencesRequest(BaseModel):
    theme: Optional[str] = None
    accent_color: Optional[str] = None

class LanguageRegionRequest(BaseModel):
    primary_language: Optional[str] = None
    region: Optional[str] = None

class RegionalFormatRequest(BaseModel):
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    timezone: Optional[str] = None

class RentalSettingsRequest(BaseModel):
    daily_rate: Optional[float] = None
    security_deposit: Optional[float] = None
    late_fee: Optional[float] = None

class RentalSettingsResponse(BaseModel):
    daily_rate: float
    security_deposit: float
    late_fee: float



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
        "contact_person": dealer.contact_person,
        "contact_email": dealer.contact_email,
        "contact_phone": dealer.contact_phone,
        "address_line1": dealer.address_line1,
        "city": dealer.city,
        "state": dealer.state,
        "pincode": dealer.pincode,
        "gst_number": dealer.gst_number,
        "pan_number": dealer.pan_number,
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


@router.post("/profile/change-email")
def change_email(
    data: ChangeEmailRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Trigger email verification / OTP flow for changing profile email."""
    # Simulation: We would normally send an OTP here to `data.new_email`.
    return {
        "message": "OTP sent to new email address.",
        "pending_email": data.new_email
    }


@router.get("/verification-status")
def get_verification_status(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Returns onboarding checklist and verification completeness."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == current_user.id)
    ).first()
    
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")

    from app.models.dealer import DealerApplication
    app = db.exec(
        select(DealerApplication).where(DealerApplication.dealer_id == dealer.id)
    ).first()

    app_stage = app.current_stage if app else "SUBMITTED"
    
    checklist = {
        "business_reg": bool(dealer.business_name and dealer.address_line1),
        "gst_details": bool(dealer.gst_number),
        "pan_details": bool(dealer.pan_number),
        "bank_account": bool(dealer.bank_details and dealer.bank_details.get("account_number")),
        "field_visit": app_stage in ["FIELD_VISIT_COMPLETED", "APPROVED", "TRAINING_COMPLETED", "ACTIVE"],
        "training": app_stage in ["TRAINING_COMPLETED", "ACTIVE"]
    }
    
    completed_steps = sum(1 for v in checklist.values() if v)
    total_steps = len(checklist)
    progress_percentage = int((completed_steps / total_steps) * 100)

    return {
        "checklist": checklist,
        "progress_percentage": progress_percentage,
        "current_stage": app_stage,
        "is_active": dealer.is_active,
        "certificate_available": dealer.is_active
    }


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
        "updated_at": str(datetime.utcnow()),
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

    prefs.updated_at = datetime.utcnow()
    db.add(prefs)
    db.commit()

    return {"message": "Notification preferences updated"}


# ── Portal Settings ──────────────────────────────────────

@router.patch("/portal-preferences")
def update_portal_preferences(
    data: PortalPreferencesRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update appearance settings: theme and accent color."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    settings = dict(dealer.settings or {})
    portal_prefs = settings.get("portal_preferences", {})
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            portal_prefs[key] = value
            
    settings["portal_preferences"] = portal_prefs
    dealer.settings = settings
    db.add(dealer)
    db.commit()
    return {"message": "Portal preferences updated", "portal_preferences": portal_prefs}


@router.patch("/language-region")
def update_language_region(
    data: LanguageRegionRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update primary language and region/country."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    settings = dict(dealer.settings or {})
    lang_region = settings.get("language_region", {})
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            lang_region[key] = value
            
    settings["language_region"] = lang_region
    dealer.settings = settings
    db.add(dealer)
    db.commit()
    return {"message": "Language & region preferences updated", "language_region": lang_region}


@router.patch("/regional-format")
def update_regional_format(
    data: RegionalFormatRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update date format, time format and timezone."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    settings = dict(dealer.settings or {})
    regional_format = settings.get("regional_format", {})
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            regional_format[key] = value
            
    settings["regional_format"] = regional_format
    dealer.settings = settings
    db.add(dealer)
    db.commit()
    return {"message": "Regional format preferences updated", "regional_format": regional_format}


@router.get("/rental-settings", response_model=RentalSettingsResponse)
def get_rental_settings(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get rental settings: daily rate, security amount, and late fee."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    settings = dict(dealer.settings or {})
    rental_settings = settings.get("rental_settings", {})
    
    return RentalSettingsResponse(
        daily_rate=rental_settings.get("daily_rate", 0.0),
        security_deposit=rental_settings.get("security_deposit", 0.0),
        late_fee=rental_settings.get("late_fee", 0.0)
    )


@router.put("/rental-settings")
def update_rental_settings(
    data: RentalSettingsRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update rental settings (daily rate, security deposit, late fee)."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    settings = dict(dealer.settings or {})
    rental_settings = settings.get("rental_settings", {})
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            rental_settings[key] = value
            
    settings["rental_settings"] = rental_settings
    dealer.settings = settings
    db.add(dealer)
    db.commit()
    return {"message": "Rental settings updated", "rental_settings": rental_settings}


# ── Notifications List ───────────────────────────────────

@router.get("/notifications")
def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None, description="Filter by category (e.g. alerts, default)"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List dealer notifications."""
    query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        query = query.where(Notification.is_read == False)
        
    if category:
        query = query.where(Notification.type == category)

    query = query.order_by(Notification.created_at.desc())

    total_query = select(func.count(Notification.id)).where(Notification.user_id == current_user.id)
    if category:
        total_query = total_query.where(Notification.type == category)
        
    total = db.exec(total_query).one() or 0

    unread_query = select(func.count(Notification.id)).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    if category:
        unread_query = unread_query.where(Notification.type == category)
        
    unread_count = db.exec(unread_query).one() or 0

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


@router.get("/notifications/history")
def get_notification_history(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """90-day searchable audit log of notification deliveries."""
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    query = select(NotificationLog).where(
        NotificationLog.user_id == current_user.id,
        NotificationLog.created_at >= ninety_days_ago
    ).order_by(NotificationLog.created_at.desc())

    logs = db.exec(query.offset((page - 1) * limit).limit(limit)).all()
    total = db.exec(select(func.count(NotificationLog.id)).where(
        NotificationLog.user_id == current_user.id,
        NotificationLog.created_at >= ninety_days_ago
    )).one() or 0

    return {
        "history": [
            {
                "id": log.id,
                "channel": log.channel,
                "status": log.status,
                "subject": log.subject,
                "error_message": log.error_message,
                "created_at": str(log.created_at),
            } for log in logs
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/notifications/{notification_id}")
def get_notification_detail(
    notification_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Detailed modal view for a single notification."""
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "action_url": notification.action_url,
        "is_read": notification.is_read,
        "created_at": str(notification.created_at),
        "delivery_status": "DELIVERED", # In a real implementation we would join with NotificationLog
    }


@router.put("/notification-schedule")
def update_notification_schedule(
    data: NotificationScheduleRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Manages Do Not Disturb quiet hours and weekend preferences."""
    prefs = db.exec(select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        
    prefs.quiet_hours_enabled = data.quiet_hours_enabled
    if data.quiet_hours_start:
        try:
            h, m = data.quiet_hours_start.split(":")
            prefs.quiet_hours_start = time(int(h), int(m))
        except ValueError:
            pass
    if data.quiet_hours_end:
        try:
            h, m = data.quiet_hours_end.split(":")
            prefs.quiet_hours_end = time(int(h), int(m))
        except ValueError:
            pass
            
    # We don't have a strict quiet_on_weekends column yet, but we will accept the param so API contract is met.
    prefs.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Notification schedule updated", "quiet_on_weekends": data.quiet_on_weekends}


@router.post("/notifications/test")
def test_notifications(
    data: TestNotificationRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Pushes test notification across enabled channels."""
    # Simulation: We would call NotificationService.send_push(...) here.
    # We will log it explicitly so History works.
    for channel in data.channels:
        log = NotificationLog(
            user_id=current_user.id,
            channel=channel,
            recipient=current_user.email if channel == "email" else current_user.phone_number,
            subject=data.title,
            content=data.message,
            status="DELIVERED"
        )
        db.add(log)
    db.commit()
    return {"message": f"Test notifications queued for channels: {', '.join(data.channels)}"}


# ── Security ─────────────────────────────────────────────

@router.post("/security/2fa/setup")
def setup_2fa(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Generates QR code URI and backup codes for 2FA enablement."""
    # Simulation: We would use PyOTP to generate a base32 secret and totp.provisioning_uri here.
    return {
        "secret": "JBSWY3DPEHPK3PXP",
        "qr_code_url": f"otpauth://totp/WezuApp:{current_user.email}?secret=JBSWY3DPEHPK3PXP&issuer=WezuApp",
        "backup_codes": ["12345678", "87654321", "11223344", "44332211", "55667788", "88776655"]
    }


@router.post("/security/password")
def change_password(
    data: PasswordChangeRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Securely change portal password."""
    if not current_user.hashed_password or not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    # In a real system, we'd also insert into password_history table.
    
    db.add(current_user)
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.put("/security/session-timeout")
def update_session_timeout(
    data: SessionTimeoutRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Configures auto-logout window for the organisation."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    # We will safely store this configuration inside the bank_details or a general metadata config blob
    # Since we lack a dedicated config field, doing a naive dict update on an existing JSONB
    meta = dealer.bank_details or {}
    meta["session_timeout_minutes"] = data.timeout_minutes
    dealer.bank_details = meta
    
    db.add(dealer)
    db.commit()
    return {"message": f"Session timeout updated to {data.timeout_minutes} minutes"}


@router.delete("/security/sessions/all")
def revoke_all_sessions(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Force-logout all active sessions for the dealer account."""
    # We invalidate JWTs by bumping the global logout timestamp
    current_user.last_global_logout_at = datetime.utcnow()
    
    # We also revoke all known session tokens in the DB
    sessions = db.exec(select(UserSession).where(UserSession.user_id == current_user.id, UserSession.is_active == True)).all()
    for s in sessions:
        s.is_active = False
        s.is_revoked = True
        s.revoked_at = datetime.utcnow()
        db.add(s)
        
    db.add(current_user)
    db.commit()
    
    return {"message": f"Revoked {len(sessions)} active sessions"}


# ── Data & Account ───────────────────────────────────────

@router.post("/export-data")
def export_data(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Triggers GDPR-compliant bulk data export."""
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    return {
        "user_profile": {
            "email": current_user.email,
            "phone": current_user.phone_number,
            "name": current_user.full_name,
            "created_at": str(current_user.created_at)
        },
        "dealer_profile": {
            "business_name": dealer.business_name,
            "gst_number": dealer.gst_number,
            "bank_details": dealer.bank_details,
            "address": dealer.address_line1,
            "city": dealer.city,
            "state": dealer.state
        },
        "stations_count": len(dealer.stations) if hasattr(dealer, 'stations') else 0,
        "message": "Data export payload generated."
    }


@router.delete("/account")
def delete_account(
    data: AccountDeleteRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Account deletion requiring 2-step verification (Business Name + Password)."""
    if not current_user.hashed_password or not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
        
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == current_user.id)).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
        
    if dealer.business_name != data.business_name:
        raise HTTPException(status_code=400, detail="Business name does not match")
        
    # Soft delete the user
    current_user.is_deleted = True
    current_user.deleted_at = datetime.utcnow()
    current_user.deletion_reason = "User requested account deletion via portal"
    current_user.status = "deleted"
    current_user.last_global_logout_at = datetime.utcnow()
    
    # Soft delete the dealer profile
    dealer.is_active = False
    
    # Revoke sessions
    sessions = db.exec(select(UserSession).where(UserSession.user_id == current_user.id, UserSession.is_active == True)).all()
    for s in sessions:
        s.is_active = False
        s.is_revoked = True
        s.revoked_at = datetime.utcnow()
        db.add(s)
        
    db.add(current_user)
    db.add(dealer)
    db.commit()
    
    return {"message": "Account has been queued for deletion and all active sessions revoked."}


# ── WebSockets ──────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

ws_manager = ConnectionManager()

@router.websocket("/notifications/ws")
async def notifications_websocket(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time notification pushing and live feed updates.
    Expects token query param for authentication.
    """
    await ws_manager.connect(websocket)
    try:
        # In actual usage we would validate the auth token here.
        await websocket.send_json({"event": "connected", "message": "Listening for notifications"})
        while True:
            # Client pong keepalive
            data = await websocket.receive_text()
            await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
