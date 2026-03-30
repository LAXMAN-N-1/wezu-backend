"""Notification Admin schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class PushCampaignCreate(BaseModel):
    title: str
    message: str
    target_segment: str = "all"
    channel: str = "push"
    scheduled_at: Optional[datetime] = None

class PushCampaignRead(BaseModel):
    id: int
    title: str
    message: str
    target_segment: str
    target_count: int
    channel: str
    status: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    sent_count: int
    delivered_count: int
    open_count: int
    click_count: int
    failed_count: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AutomatedTriggerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    event_type: str
    channel: str = "push"
    template_message: str
    delay_minutes: int = 0
    is_active: bool = True

class AutomatedTriggerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    channel: Optional[str] = None
    template_message: Optional[str] = None
    delay_minutes: Optional[int] = None
    is_active: Optional[bool] = None

class AutomatedTriggerRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    event_type: str
    channel: str
    template_message: str
    delay_minutes: int
    is_active: bool
    trigger_count: int
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationLogRead(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    trigger_id: Optional[int] = None
    user_id: Optional[int] = None
    channel: str
    title: str
    message: str
    status: str
    error_message: Optional[str] = None
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class NotificationConfigCreate(BaseModel):
    provider: str
    channel: str
    display_name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sender_id: Optional[str] = None

class NotificationConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sender_id: Optional[str] = None
    is_active: Optional[bool] = None

class NotificationConfigRead(BaseModel):
    id: int
    provider: str
    channel: str
    display_name: str
    api_key: Optional[str] = None  # Will be masked in response
    sender_id: Optional[str] = None
    is_active: bool
    last_tested_at: Optional[datetime] = None
    test_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
