from pydantic import BaseModel
from datetime import datetime, time
from typing import Optional

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    channel: str
    payload: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Notification Preferences Schemas
class QuietHours(BaseModel):
    """Quiet hours settings - when user should not be disturbed."""
    enabled: bool = False
    start_time: str = "22:00"  # 24-hour format HH:MM
    end_time: str = "07:00"    # 24-hour format HH:MM
    timezone: str = "UTC"


class EmailPreferences(BaseModel):
    enabled: bool = True  # Master toggle for email channel
    rental_confirmations: bool = True
    payment_receipts: bool = True
    promotional: bool = False
    security_alerts: bool = True


class SMSPreferences(BaseModel):
    enabled: bool = True  # Master toggle for SMS channel
    rental_confirmations: bool = True
    payment_receipts: bool = False
    otp: bool = True


class PushPreferences(BaseModel):
    enabled: bool = True  # Master toggle for push channel
    battery_available: bool = True
    payment_reminders: bool = True
    promotional: bool = False


class NotificationPreferencesResponse(BaseModel):
    email: EmailPreferences
    sms: SMSPreferences
    push: PushPreferences
    quiet_hours: QuietHours


class NotificationPreferencesUpdate(BaseModel):
    """Request body to update notification preferences (partial updates allowed)."""
    email: Optional[EmailPreferences] = None
    sms: Optional[SMSPreferences] = None
    push: Optional[PushPreferences] = None
    quiet_hours: Optional[QuietHours] = None

# --- New Gaps Schemas ---
class AdminNotificationSendRequest(BaseModel):
    user_id: Optional[int] = None
    segment: Optional[str] = None # all, dealers, drivers, customers
    title: str
    message: str
    type: str = "info"
    channel: str = "push"

class UnreadCountResponse(BaseModel):
    unread_count: int
