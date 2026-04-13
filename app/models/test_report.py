from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from typing import Optional, Any
from datetime import datetime, timezone, timedelta


# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    """Return current time as naive datetime representing IST.
    This ensures the literal local time (e.g. 19:02) is stored and visible in the DB console.
    """
    return datetime.now(IST).replace(tzinfo=None)


class TestReport(SQLModel, table=True):
    __tablename__ = "test_reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_by: str = Field(default="dev", max_length=255)
    module_name: str = Field(max_length=255)
    total_tests: int
    passed: int
    failed: int

    # JSON columns for failures/errors detail
    failures: Optional[Any] = Field(default=None, sa_column=Column(JSON, nullable=True))
    errors: Optional[Any] = Field(default=None, sa_column=Column(JSON, nullable=True))

    # Execution info
    execution_time: str = Field(max_length=50)
    environment: str = Field(default="local", max_length=50)

    # Timestamps — recorded in IST (Asia/Kolkata, UTC+5:30)
    created_at: Optional[datetime] = Field(default_factory=_now_ist)
