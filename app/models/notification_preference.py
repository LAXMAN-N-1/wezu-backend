from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import time, datetime, UTC
from app.models import *

class NotificationPreference(SQLModel, table=True):
    __tablename__ = "notification_preferences"
    """User notification settings per channel and category"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    
    # Global settings
    notifications_enabled: bool = Field(default=True)
    
    # Channel preferences
    push_enabled: bool = Field(default=True)
    email_enabled: bool = Field(default=True)
    sms_enabled: bool = Field(default=False)
    whatsapp_enabled: bool = Field(default=False)
    
    # Category preferences (each can be enabled/disabled per channel)
    # Transactional (cannot be disabled)
    transactional_push: bool = Field(default=True)
    transactional_email: bool = Field(default=True)
    transactional_sms: bool = Field(default=True)
    
    # Promotional
    promotional_push: bool = Field(default=True)
    promotional_email: bool = Field(default=True)
    promotional_sms: bool = Field(default=False)
    
    # Battery alerts
    battery_alerts_push: bool = Field(default=True)
    battery_alerts_email: bool = Field(default=False)
    battery_alerts_sms: bool = Field(default=False)
    
    # Rental reminders
    rental_reminders_push: bool = Field(default=True)
    rental_reminders_email: bool = Field(default=True)
    rental_reminders_sms: bool = Field(default=False)
    
    # Payment notifications
    payment_push: bool = Field(default=True)
    payment_email: bool = Field(default=True)
    payment_sms: bool = Field(default=True)
    
    # Swap suggestions
    swap_suggestions_push: bool = Field(default=True)
    swap_suggestions_email: bool = Field(default=False)
    
    # Maintenance updates
    maintenance_push: bool = Field(default=True)
    maintenance_email: bool = Field(default=False)
    
    # Marketing & offers
    marketing_push: bool = Field(default=False)
    marketing_email: bool = Field(default=False)
    marketing_sms: bool = Field(default=False)
    
    # Frequency capping
    max_push_per_day: int = Field(default=20)
    max_email_per_day: int = Field(default=5)
    max_sms_per_day: int = Field(default=3)
    
    # Quiet hours (no non-critical notifications)
    quiet_hours_enabled: bool = Field(default=False)
    quiet_hours_start: Optional[time] = None  # e.g., 22:00
    quiet_hours_end: Optional[time] = None    # e.g., 08:00
    
    # Language preference
    preferred_language: str = Field(default="en")  # en, hi, etc.
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: "User" = Relationship(back_populates="notification_preference")
