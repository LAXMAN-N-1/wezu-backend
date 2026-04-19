from __future__ import annotations
"""
System configuration and feature flag schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── SystemConfig ─────────────────────────────────────────

class SystemConfigCreate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class SystemConfigUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None

class SystemConfigResponse(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── FeatureFlag ──────────────────────────────────────────

class FeatureFlagCreate(BaseModel):
    name: str
    is_enabled: bool = False
    rollout_percentage: int = 0
    enabled_for_users: Optional[str] = None
    enabled_for_tenants: Optional[str] = None

class FeatureFlagUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = None
    enabled_for_users: Optional[str] = None
    enabled_for_tenants: Optional[str] = None

class FeatureFlagResponse(BaseModel):
    id: int
    name: str
    is_enabled: bool
    rollout_percentage: int = 0
    enabled_for_users: Optional[str] = None
    enabled_for_tenants: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FeatureFlagListResponse(BaseModel):
    flags: List[FeatureFlagResponse]
    total_count: int
