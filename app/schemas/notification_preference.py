"""
NotificationPreference schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, time


class NotificationPreferenceUpdate(BaseModel):
    notifications_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None

    # Category-specific
    transactional_push: Optional[bool] = None
    transactional_email: Optional[bool] = None
    transactional_sms: Optional[bool] = None
    promotional_push: Optional[bool] = None
    promotional_email: Optional[bool] = None
    promotional_sms: Optional[bool] = None
    battery_alerts_push: Optional[bool] = None
    battery_alerts_email: Optional[bool] = None
    battery_alerts_sms: Optional[bool] = None
    rental_reminders_push: Optional[bool] = None
    rental_reminders_email: Optional[bool] = None
    rental_reminders_sms: Optional[bool] = None
    payment_push: Optional[bool] = None
    payment_email: Optional[bool] = None
    payment_sms: Optional[bool] = None
    swap_suggestions_push: Optional[bool] = None
    swap_suggestions_email: Optional[bool] = None
    maintenance_push: Optional[bool] = None
    maintenance_email: Optional[bool] = None
    marketing_push: Optional[bool] = None
    marketing_email: Optional[bool] = None
    marketing_sms: Optional[bool] = None

    # Rate Limits
    max_push_per_day: Optional[int] = None
    max_email_per_day: Optional[int] = None
    max_sms_per_day: Optional[int] = None

    # Quiet Hours
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None

    preferred_language: Optional[str] = None


class NotificationPreferenceResponse(BaseModel):
    id: int
    user_id: int
    notifications_enabled: bool = True
    push_enabled: bool = True
    email_enabled: bool = True
    sms_enabled: bool = True
    whatsapp_enabled: bool = False

    transactional_push: bool = True
    transactional_email: bool = True
    transactional_sms: bool = True
    promotional_push: bool = True
    promotional_email: bool = True
    promotional_sms: bool = False
    battery_alerts_push: bool = True
    battery_alerts_email: bool = True
    battery_alerts_sms: bool = False
    rental_reminders_push: bool = True
    rental_reminders_email: bool = True
    rental_reminders_sms: bool = False
    payment_push: bool = True
    payment_email: bool = True
    payment_sms: bool = True
    swap_suggestions_push: bool = True
    swap_suggestions_email: bool = False
    maintenance_push: bool = True
    maintenance_email: bool = True
    marketing_push: bool = True
    marketing_email: bool = True
    marketing_sms: bool = False

    max_push_per_day: int = 10
    max_email_per_day: int = 5
    max_sms_per_day: int = 3

    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None

    preferred_language: str = "en"
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
