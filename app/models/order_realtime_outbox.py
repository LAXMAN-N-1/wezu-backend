from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class OrderRealtimeOutbox(SQLModel, table=True):
    __tablename__ = "order_realtime_outbox"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: str = Field(foreign_key="logistics_orders.id", index=True)
    event_type: str = Field(index=True)
    payload: str
    status: str = Field(default="pending", index=True)  # pending, processing, published, failed
    attempt_count: int = Field(default=0)
    max_attempts: int = Field(default=10)
    last_error: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    next_attempt_at: Optional[datetime] = Field(default_factory=datetime.utcnow, index=True)
    published_at: Optional[datetime] = None
