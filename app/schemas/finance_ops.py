from __future__ import annotations
"""
Late fee, chargeback, refund, and promo code schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Late Fee ─────────────────────────────────────────────

class LateFeeResponse(BaseModel):
    id: int
    rental_id: int
    amount: float
    currency: str = "INR"
    status: str = "pending"
    waived: bool = False
    waiver_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LateFeeWaiverCreate(BaseModel):
    late_fee_id: int
    reason: str

class LateFeeWaiverResponse(BaseModel):
    id: int
    late_fee_id: int
    reason: str
    approved_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Chargeback ───────────────────────────────────────────

class ChargebackCreate(BaseModel):
    settlement_id: int
    amount: float
    reason: str
    evidence_url: Optional[str] = None

class ChargebackResponse(BaseModel):
    id: int
    settlement_id: int
    amount: float
    reason: str
    status: str = "pending"
    evidence_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Refund ───────────────────────────────────────────────

class RefundCreate(BaseModel):
    transaction_id: int
    amount: float
    reason: str

class RefundResponse(BaseModel):
    id: int
    transaction_id: int
    amount: float
    reason: str
    status: str = "pending"
    processed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── PromoCode ────────────────────────────────────────────

class PromoCodeCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str  # percentage, flat
    discount_value: float
    max_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

class PromoCodeResponse(BaseModel):
    id: int
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    max_uses: Optional[int] = None
    current_uses: int = 0
    is_active: bool = True
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Referral ─────────────────────────────────────────────

class ReferralResponse(BaseModel):
    id: int
    referrer_id: int
    referee_id: Optional[int] = None
    referral_code: str
    status: str = "pending"
    reward_amount: float = 0.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Revenue Report ───────────────────────────────────────

class RevenueReportResponse(BaseModel):
    id: int
    report_type: str
    period: str
    total_revenue: float = 0.0
    total_commissions: float = 0.0
    total_refunds: float = 0.0
    net_revenue: float = 0.0
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
