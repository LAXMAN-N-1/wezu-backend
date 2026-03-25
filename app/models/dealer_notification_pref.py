from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, time
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

class QuietHours(SQLModel):
    """Not a table, just a Pydantic model structure used in JSON"""
    start: str = "22:00"
    end: str = "07:00"

class DealerNotificationPreference(SQLModel, table=True):
    __tablename__ = "dealer_notification_prefs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id", unique=True)
    
    # Alert Toggles
    low_inventory_alert: bool = Field(default=True)
    low_inventory_threshold: int = Field(default=5)
    
    maintenance_due_alert: bool = Field(default=True)
    maintenance_reminder_days: int = Field(default=3)
    
    new_booking_alert: bool = Field(default=True)
    support_ticket_alert: bool = Field(default=True)
    
    # Digests
    daily_summary_email: bool = Field(default=True)
    weekly_report_email: bool = Field(default=True)
    
    # Channel Toggles
    sms_notifications: bool = Field(default=False)
    push_notifications: bool = Field(default=True)
    
    # Quiet Hours (stored as JSON)
    # e.g., {"start": "22:00", "end": "07:00"}
    quiet_hours_enabled: bool = Field(default=False) # Helper toggle (internal, not in spec but good to have)
    quiet_hours: Optional[dict] = Field(default_factory=lambda: {"start": "22:00", "end": "07:00"}, sa_column=sa.Column(sa.JSON().with_variant(JSONB, "postgresql")))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # We could link back to dealer if we want, but unique dealer_id is enough for the service
