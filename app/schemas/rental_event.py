from __future__ import annotations
"""
Rental event and modification schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── RentalEvent ──────────────────────────────────────────

class RentalEventResponse(BaseModel):
    id: int
    rental_id: int
    event_type: str
    description: Optional[str] = None
    station_id: Optional[int] = None
    battery_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── RentalExtension ──────────────────────────────────────

class RentalExtensionCreate(BaseModel):
    rental_id: int
    new_end_time: datetime
    reason: Optional[str] = None

class RentalExtensionResponse(BaseModel):
    id: int
    rental_id: int
    original_end_time: datetime
    new_end_time: datetime
    additional_cost: float = 0.0
    reason: Optional[str] = None
    status: str = "pending"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── RentalPause ──────────────────────────────────────────

class RentalPauseCreate(BaseModel):
    rental_id: int
    reason: Optional[str] = None

class RentalPauseResponse(BaseModel):
    id: int
    rental_id: int
    paused_at: datetime
    resumed_at: Optional[datetime] = None
    reason: Optional[str] = None
    status: str = "paused"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
