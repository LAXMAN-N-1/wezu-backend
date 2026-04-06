from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AnalyticsActivityEvent(SQLModel, table=True):
    __tablename__ = "analytics_activity_events"

    id: str = Field(primary_key=True)
    event_type: str = Field(index=True)
    title: str
    event_timestamp: datetime = Field(index=True)
    reference_id: Optional[str] = Field(default=None, index=True)
    meta_json: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyticsReportJob(SQLModel, table=True):
    __tablename__ = "analytics_report_jobs"

    report_id: str = Field(primary_key=True)
    status: str = Field(default="queued", index=True)  # queued|processing|completed|failed
    report_format: str = Field(default="csv")
    timezone: str = Field(default="UTC")
    include_sections: str = Field(default="[]")  # JSON list
    from_utc: datetime
    to_utc: datetime

    requested_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")

    file_path: Optional[str] = None
    file_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    detail: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
