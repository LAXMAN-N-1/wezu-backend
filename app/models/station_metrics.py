from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class StationDailyMetric(SQLModel, table=True):
    __tablename__ = "station_daily_metrics"
    __table_args__ = (UniqueConstraint("station_id", "metric_date", name="uq_station_daily_metrics_station_date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id", index=True)
    metric_date: date = Field(index=True)
    rentals_started: int = Field(default=0)
    rentals_completed: int = Field(default=0)
    average_duration_minutes: Optional[float] = None
    refreshed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
