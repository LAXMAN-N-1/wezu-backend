from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone; UTC = timezone.utc
from sqlmodel import SQLModel, Field


class Chargeback(SQLModel, table=True):
    """Records chargebacks against dealer earnings, deducted during settlement."""
    __tablename__ = "chargebacks"
    id: Optional[int] = Field(default=None, primary_key=True)

    dealer_id: int = Field(foreign_key="users.id", index=True)
    swap_session_id: Optional[int] = Field(default=None, foreign_key="swap_sessions.id")

    amount: float
    reason: str  # e.g. "customer_refund", "damaged_battery", "fraud"
    status: str = Field(default="pending")  # pending, deducted, reversed

    # Settlement linkage (filled when deducted)
    settlement_id: Optional[int] = Field(default=None, foreign_key="settlements.id")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
