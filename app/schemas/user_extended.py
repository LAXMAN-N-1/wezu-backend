from __future__ import annotations
"""
Membership, search history, and user profile schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# ── UserProfile ──────────────────────────────────────────

class UserProfileUpdate(BaseModel):
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact: Optional[str] = None

class UserProfileResponse(BaseModel):
    id: int
    user_id: int
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Membership ───────────────────────────────────────────

class UserMembershipResponse(BaseModel):
    id: int
    user_id: int
    tier: str = "basic"
    points_balance: float = 0.0
    status: str = "active"
    tier_expiry: Optional[datetime] = None
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Search History ───────────────────────────────────────

class SearchHistoryResponse(BaseModel):
    id: int
    user_id: int
    query: str
    search_type: Optional[str] = None
    results_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SearchHistoryListResponse(BaseModel):
    searches: List[SearchHistoryResponse]
    total_count: int


# ── Login History ────────────────────────────────────────

class LoginHistoryResponse(BaseModel):
    id: int
    user_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    success: bool = True
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Swap Suggestion ──────────────────────────────────────

class SwapSuggestionResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    current_battery_id: Optional[int] = None
    suggested_station_id: Optional[int] = None
    reason: Optional[str] = None
    priority: int = 0
    is_dismissed: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SwapPreferenceUpdate(BaseModel):
    preferred_charge_level: Optional[float] = None
    max_distance_km: Optional[float] = None
    preferred_station_ids: Optional[List[int]] = None

class SwapPreferenceResponse(BaseModel):
    id: int
    user_id: int
    preferred_charge_level: float = 80.0
    max_distance_km: float = 10.0
    preferred_station_ids: Optional[List[int]] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Batch Job ────────────────────────────────────────────

class BatchJobResponse(BaseModel):
    id: int
    job_type: str
    status: str = "queued"
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class JobExecutionResponse(BaseModel):
    id: int
    batch_job_id: int
    item_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
