from datetime import datetime, UTC
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class CommissionConfig(SQLModel, table=True):
    __tablename__ = "commission_configs"
    id: Optional[int] = Field(default=None, primary_key=True)

    # Target entity
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id")

    # Type of transaction
    transaction_type: str = Field(index=True)  # rental, swap, purchase

    # Default Commission Rate (used when no tier matches)
    percentage: float = Field(default=0.0)
    flat_fee: float = Field(default=0.0)

    # Effective date management
    effective_from: datetime = Field(default_factory=lambda: datetime.now(UTC))
    effective_until: Optional[datetime] = Field(default=None)

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CommissionTier(SQLModel, table=True):
    """Volume-based commission tiers linked to a CommissionConfig."""
    __tablename__ = "commission_tiers"
    id: Optional[int] = Field(default=None, primary_key=True)

    config_id: int = Field(foreign_key="commission_configs.id", index=True)

    # Volume range (number of swaps/transactions in the month)
    min_volume: int = Field(default=0)
    max_volume: Optional[int] = Field(default=None)  # None = unlimited

    # Tier-specific rate
    percentage: float = Field(default=0.0)
    flat_fee: float = Field(default=0.0)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CommissionLog(SQLModel, table=True):
    __tablename__ = "commission_logs"
    id: Optional[int] = Field(default=None, primary_key=True)

    # Reference to causing event
    transaction_id: int = Field(foreign_key="transactions.id")

    # Beneficiary
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id")

    # Earnings
    amount: float
    status: str = Field(default="pending")  # pending, paid, reversed

    # Settlement linkage
    settlement_id: Optional[int] = Field(default=None, foreign_key="settlements.id")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    settlement: Optional["Settlement"] = Relationship(back_populates="commission_logs")

