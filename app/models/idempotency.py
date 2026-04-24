from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            "request_method",
            "request_path",
            name="uq_idempotency_user_scope",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    idempotency_key: str = Field(index=True)
    request_method: str
    request_path: str
    request_fingerprint: str
    response_status_code: int
    response_payload: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=48))
