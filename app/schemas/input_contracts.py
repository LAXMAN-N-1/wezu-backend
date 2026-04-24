from __future__ import annotations
"""
P4-B: Typed request schemas replacing raw `dict` body parameters.

These schemas enforce field-level validation on all POST/PUT/PATCH
endpoints that previously accepted untyped `dict` input.
"""

from pydantic import BaseModel, Field
from typing import Optional, Union
from datetime import datetime


# ── Profile ───────────────────────────────────────────────────────────

class PreferencesUpdate(BaseModel):
    """User notification preference partial update."""
    notifications_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None

    promotional_push: Optional[bool] = None
    promotional_email: Optional[bool] = None
    promotional_sms: Optional[bool] = None

    battery_alerts_push: Optional[bool] = None
    battery_alerts_email: Optional[bool] = None
    battery_alerts_sms: Optional[bool] = None

    rental_reminders_push: Optional[bool] = None
    rental_reminders_email: Optional[bool] = None
    rental_reminders_sms: Optional[bool] = None

    payment_push: Optional[bool] = None
    payment_email: Optional[bool] = None
    payment_sms: Optional[bool] = None

    swap_suggestions_push: Optional[bool] = None
    swap_suggestions_email: Optional[bool] = None

    maintenance_push: Optional[bool] = None
    maintenance_email: Optional[bool] = None

    marketing_push: Optional[bool] = None
    marketing_email: Optional[bool] = None
    marketing_sms: Optional[bool] = None

    max_push_per_day: Optional[int] = Field(None, ge=0, le=100)
    max_email_per_day: Optional[int] = Field(None, ge=0, le=50)
    max_sms_per_day: Optional[int] = Field(None, ge=0, le=20)

    quiet_hours_enabled: Optional[bool] = None
    preferred_language: Optional[str] = Field(None, min_length=2, max_length=5)


class ChangePasswordRequest(BaseModel):
    """Password change payload."""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


# ── Dealer ────────────────────────────────────────────────────────────

class DealerPromotionCreate(BaseModel):
    """Create a dealer promotion campaign."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    promo_code: str = Field(..., min_length=3, max_length=50)
    discount_type: str = Field(..., description="PERCENTAGE, FIXED_AMOUNT | FREE_DELIVERY")
    discount_value: float = Field(..., gt=0)
    min_purchase_amount: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    budget_limit: Optional[float] = Field(None, ge=0)
    daily_cap: Optional[int] = Field(None, ge=0)
    usage_limit_total: Optional[int] = Field(None, ge=0)
    usage_limit_per_user: int = Field(1, ge=1)
    applicable_to: str = Field("ALL", description="ALL, RENTAL | PURCHASE | SPECIFIC_MODELS")
    applicable_station_ids: Optional[str] = None
    applicable_models: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True


class DealerPromotionUpdate(BaseModel):
    """Update / deactivate a dealer promotion."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    discount_value: Optional[float] = Field(None, gt=0)
    max_discount_amount: Optional[float] = Field(None, ge=0)
    budget_limit: Optional[float] = Field(None, ge=0)
    daily_cap: Optional[int] = Field(None, ge=0)
    usage_limit_total: Optional[int] = Field(None, ge=0)
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class BankAccountUpdate(BaseModel):
    """Dealer bank account details."""
    account_holder_name: str = Field(..., min_length=1, max_length=200)
    account_number: str = Field(..., min_length=5, max_length=30)
    ifsc_code: str = Field(..., min_length=8, max_length=15)
    bank_name: str = Field(..., min_length=1, max_length=200)
    branch: Optional[str] = Field(None, max_length=200)
    upi_id: Optional[str] = Field(None, max_length=100)


# ── Dealer Portal ────────────────────────────────────────────────────

class NotificationPreferencesUpdate(BaseModel):
    """Dealer-side notification preference update.

    Accepts the same fields as the NotificationPreference model
    (minus id, user_id, and relationships).
    """
    notifications_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    maintenance_push: Optional[bool] = None
    maintenance_email: Optional[bool] = None
    preferred_language: Optional[str] = Field(None, min_length=2, max_length=5)


class DealerDocumentUpload(BaseModel):
    """Upload metadata for a dealer document."""
    document_type: str = Field("other", max_length=50)
    category: str = Field("verification", max_length=50)
    file_url: str = Field(..., min_length=1, max_length=500)
    valid_until: Optional[str] = Field(None, description="ISO 8601 date string")


# ── Station ──────────────────────────────────────────────────────────

class MaintenanceTaskCreate(BaseModel):
    """Create a station maintenance task."""
    maintenance_type: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    priority: str = Field("medium", description="low, medium | high | critical")
    scheduled_at: Optional[datetime] = None
