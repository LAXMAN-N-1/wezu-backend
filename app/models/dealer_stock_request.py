"""
Dealer Stock Request model — tracks stock replenishment requests
from dealers to admin/platform.
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC
from enum import Enum


class StockRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class StockRequestPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DealerStockRequest(SQLModel, table=True):
    __tablename__ = "dealer_stock_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id", index=True)

    # What they want
    model_id: Optional[int] = Field(default=None, foreign_key="battery_catalog.id")
    model_name: Optional[str] = None  # Denormalized for quick display
    quantity: int = Field(ge=1)

    # Timeline
    delivery_date: Optional[datetime] = None  # Requested delivery date

    # Metadata
    priority: StockRequestPriority = Field(default=StockRequestPriority.NORMAL)
    reason: Optional[str] = None
    notes: Optional[str] = None

    # Status workflow
    status: StockRequestStatus = Field(default=StockRequestStatus.PENDING, index=True)

    # Admin response
    admin_notes: Optional[str] = None
    approved_by: Optional[int] = Field(default=None, foreign_key="users.id")
    approved_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None

    # Fulfillment
    fulfilled_at: Optional[datetime] = None
    fulfilled_quantity: Optional[int] = None

    # Tracking
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
