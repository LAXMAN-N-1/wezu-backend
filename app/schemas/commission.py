from __future__ import annotations
"""
Commission schemas: CommissionConfig, CommissionTier, CommissionLog
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── CommissionConfig ─────────────────────────────────────

class CommissionConfigCreate(BaseModel):
    dealer_id: Optional[int] = None
    vendor_id: Optional[int] = None
    transaction_type: str
    percentage: float = 0.0
    flat_fee: float = 0.0
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None

class CommissionConfigUpdate(BaseModel):
    percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    effective_until: Optional[datetime] = None
    is_active: Optional[bool] = None

class CommissionConfigResponse(BaseModel):
    id: int
    dealer_id: Optional[int] = None
    vendor_id: Optional[int] = None
    transaction_type: str
    percentage: float
    flat_fee: float
    effective_from: datetime
    effective_until: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── CommissionTier ───────────────────────────────────────

class CommissionTierCreate(BaseModel):
    config_id: int
    min_volume: int = 0
    max_volume: Optional[int] = None
    percentage: float = 0.0
    flat_fee: float = 0.0

class CommissionTierResponse(BaseModel):
    id: int
    config_id: int
    min_volume: int
    max_volume: Optional[int] = None
    percentage: float
    flat_fee: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── CommissionLog ────────────────────────────────────────

class CommissionLogResponse(BaseModel):
    id: int
    transaction_id: int
    dealer_id: Optional[int] = None
    vendor_id: Optional[int] = None
    amount: float
    status: str
    settlement_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CommissionLogListResponse(BaseModel):
    logs: List[CommissionLogResponse]
    total_count: int
    page: int = 1
    limit: int = 20
