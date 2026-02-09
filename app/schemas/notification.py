from pydantic import BaseModel
from datetime import datetime
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
class EmailPreferences(BaseModel):
    rental_confirmations: bool = True
    payment_receipts: bool = True
    promotional: bool = False
    security_alerts: bool = True


class SMSPreferences(BaseModel):
    rental_confirmations: bool = True
    payment_receipts: bool = False
    otp: bool = True


class PushPreferences(BaseModel):
    battery_available: bool = True
    payment_reminders: bool = True
    promotional: bool = False


class NotificationPreferencesResponse(BaseModel):
    email: EmailPreferences
    sms: SMSPreferences
    push: PushPreferences


class NotificationPreferencesUpdate(BaseModel):
    """Request body to update notification preferences (partial updates allowed)."""
    email: Optional[EmailPreferences] = None
    sms: Optional[SMSPreferences] = None
    push: Optional[PushPreferences] = None
