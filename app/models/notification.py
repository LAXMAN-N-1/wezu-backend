from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC
from enum import Enum


class NotificationStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    DEAD_LETTER = "dead_letter"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls._value2member_map_


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str
    message: str
    type: str = Field(default="info") # info, alert, promo
    channel: str = Field(default="push") # push, sms, email, whatsapp
    
    payload: Optional[str] = None # JSON data for deeplinking
    scheduled_at: Optional[datetime] = None
    status: str = Field(default="pending") # pending, sent, failed
    
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    user: "User" = Relationship()
