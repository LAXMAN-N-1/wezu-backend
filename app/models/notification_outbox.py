from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class NotificationOutboxStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return (
            cls.PENDING,
            cls.PROCESSING,
            cls.PUBLISHED,
            cls.FAILED,
            cls.DEAD_LETTER,
        )

    @classmethod
    def is_valid(cls, value: str | None) -> bool:
        return bool(value) and value in cls.values()


class NotificationOutbox(SQLModel, table=True):
    __tablename__ = "notification_outbox"

    id: Optional[int] = Field(default=None, primary_key=True)
    notification_id: int = Field(foreign_key="notification.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    channel: str = Field(index=True)
    status: str = Field(default=NotificationOutboxStatus.PENDING, index=True)
    attempt_count: int = Field(default=0)
    max_attempts: int = Field(default=10)
    last_error: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    next_attempt_at: Optional[datetime] = Field(default_factory=datetime.utcnow, index=True)
    published_at: Optional[datetime] = None
