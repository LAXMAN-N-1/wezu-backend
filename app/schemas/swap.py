from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SwapSessionBase(BaseModel):
    station_id: int
    old_battery_serial: Optional[str] = None # User might provide serial or system detects it via slot

class SwapInitRequest(SwapSessionBase):
    rental_id: Optional[int] = None
    new_battery_id: Optional[int] = None
    duration_days: Optional[int] = None
    preferred_battery_type: Optional[str] = None

class SwapResponse(BaseModel):
    id: int
    status: str
    station_id: int
    station_name: Optional[str] = None
    amount: float
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SwapCompleteRequest(BaseModel):
    new_battery_id: int
    new_battery_soc: float
    old_battery_soc: float
