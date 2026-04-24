from __future__ import annotations
"""API Key model for Settings module."""
from datetime import datetime, timezone; UTC = timezone.utc
from typing import Optional
from sqlmodel import SQLModel, Field


class ApiKeyConfig(SQLModel, table=True):
    __tablename__ = "api_key_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    service_name: str = Field(index=True)  # stripe, google_maps, twilio, firebase, sendgrid, razorpay
    key_name: str  # Display label e.g., "Stripe Live Key"
    key_value: str  # Stored value (encrypted in production)
    environment: str = Field(default="development")  # development, staging, production
    is_active: bool = Field(default=True)
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
