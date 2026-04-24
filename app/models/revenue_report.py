from __future__ import annotations
from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, date, timezone; UTC = timezone.utc
from sqlalchemy import Column, JSON


class RevenueReport(SQLModel, table=True):
    """Persisted snapshot of a revenue report (daily/weekly/monthly)."""
    __tablename__ = "revenue_reports"
    id: Optional[int] = Field(default=None, primary_key=True)

    report_type: str = Field(index=True)  # daily, weekly, monthly
    period_start: date = Field(index=True)
    period_end: date

    # Aggregate totals
    total_revenue: float = 0.0
    total_transactions: int = 0
    avg_transaction_value: float = 0.0
    total_refunds: float = 0.0
    net_revenue: float = 0.0

    # Growth
    growth_percentage: Optional[float] = None  # vs previous period

    # Breakdowns (JSON)
    breakdown_by_dealer: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("breakdown_by_dealer", JSON, nullable=True)
    )
    breakdown_by_station: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("breakdown_by_station", JSON, nullable=True)
    )
    breakdown_by_category: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("breakdown_by_category", JSON, nullable=True)
    )
    breakdown_by_source: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("breakdown_by_source", JSON, nullable=True)
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
