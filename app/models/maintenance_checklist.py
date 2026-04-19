from __future__ import annotations
from datetime import datetime, timezone; UTC = timezone.utc
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class MaintenanceChecklistTemplate(SQLModel, table=True):
    __tablename__ = "maintenance_checklist_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    station_type: str = Field(default="standard", index=True)
    maintenance_type: str = Field(default="routine", index=True)
    tasks: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql"), nullable=False),
    )
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MaintenanceChecklistSubmission(SQLModel, table=True):
    __tablename__ = "maintenance_checklist_submissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    maintenance_record_id: Optional[int] = Field(
        default=None,
        foreign_key="maintenance_records.id",
        index=True,
    )
    template_id: int = Field(foreign_key="maintenance_checklist_templates.id", index=True)
    template_version: int = Field(default=1)
    completed_tasks: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql"), nullable=False),
    )
    submitted_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    submitted_by_name: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_final: bool = Field(default=False)
