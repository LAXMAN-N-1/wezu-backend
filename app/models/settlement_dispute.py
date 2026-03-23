from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class SettlementDispute(SQLModel, table=True):
    """Dispute raised by a dealer against a settlement record."""
    __tablename__ = "settlement_disputes"
    id: Optional[int] = Field(default=None, primary_key=True)

    settlement_id: int = Field(foreign_key="settlements.id", index=True)
    dealer_id: int = Field(foreign_key="users.id", index=True)

    reason: str
    status: str = Field(default="open")  # open, under_review, resolved, rejected

    resolution_notes: Optional[str] = None
    adjustment_amount: Optional[float] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
