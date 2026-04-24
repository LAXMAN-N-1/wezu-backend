from __future__ import annotations
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel


class PaymentMethod(SQLModel, table=True):
    __tablename__ = "payment_methods"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    provider: str = Field(default="razorpay", index=True)
    method_type: str = Field(index=True)  # card, upi, netbanking, wallet
    provider_token: str = Field(index=True)
    last4: Optional[str] = None
    brand: Optional[str] = None
    metadata_json: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSON, "postgresql")))

    is_default: bool = Field(default=False)
    status: str = Field(default="active", index=True)  # active, deleted

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
