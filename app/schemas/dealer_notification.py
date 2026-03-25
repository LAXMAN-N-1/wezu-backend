from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class QuietHoursSchema(BaseModel):
    start: str = "22:00"
    end: str = "07:00"

class DealerNotificationPreferenceResponse(BaseModel):
    dealer_id: int
    low_inventory_alert: bool
    low_inventory_threshold: int
    maintenance_due_alert: bool
    maintenance_reminder_days: int
    new_booking_alert: bool
    support_ticket_alert: bool
    daily_summary_email: bool
    weekly_report_email: bool
    sms_notifications: bool
    push_notifications: bool
    quiet_hours: Optional[QuietHoursSchema] = None

class DealerNotificationPreferenceUpdate(BaseModel):
    low_inventory_alert: Optional[bool] = None
    low_inventory_threshold: Optional[int] = None
    maintenance_due_alert: Optional[bool] = None
    maintenance_reminder_days: Optional[int] = None
    new_booking_alert: Optional[bool] = None
    support_ticket_alert: Optional[bool] = None
    daily_summary_email: Optional[bool] = None
    weekly_report_email: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    quiet_hours: Optional[QuietHoursSchema] = None
