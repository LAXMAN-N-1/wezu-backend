"""Notification Admin models — Campaigns, Triggers, Logs, Config."""
from datetime import datetime, UTC
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class PushCampaign(SQLModel, table=True):
    __tablename__ = "push_campaigns"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    message: str
    target_segment: str = Field(default="all")  # all, active, inactive, custom
    target_count: int = Field(default=0)
    channel: str = Field(default="push")  # push, sms, email, whatsapp
    status: str = Field(default="draft", index=True)  # draft, scheduled, sending, sent, failed
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    sent_count: int = Field(default=0)
    delivered_count: int = Field(default=0)
    open_count: int = Field(default=0)
    click_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AutomatedTrigger(SQLModel, table=True):
    __tablename__ = "automated_triggers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    event_type: str = Field(index=True)  # inactivity, rental_reminder, payment_due, low_battery, welcome, swap_complete
    channel: str = Field(default="push")  # push, sms, email
    template_message: str
    delay_minutes: int = Field(default=0)  # Delay after event before sending
    is_active: bool = Field(default=True)
    trigger_count: int = Field(default=0)
    last_triggered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NotificationLog(SQLModel, table=True):
    __tablename__ = "notification_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: Optional[int] = Field(default=None, foreign_key="push_campaigns.id")
    trigger_id: Optional[int] = Field(default=None, foreign_key="automated_triggers.id")
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    channel: str = Field(default="push")
    title: str
    message: str
    status: str = Field(default="sent", index=True)  # sent, delivered, opened, failed, bounced
    error_message: Optional[str] = None
    sent_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None


class NotificationConfig(SQLModel, table=True):
    __tablename__ = "notification_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)  # twilio, sendgrid, firebase, smtp
    channel: str  # sms, email, push, whatsapp
    display_name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sender_id: Optional[str] = None  # Phone number, email address, etc.
    is_active: bool = Field(default=False)
    last_tested_at: Optional[datetime] = None
    test_status: Optional[str] = None  # success, failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
