from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class VehicleBase(BaseModel):
    make: str
    model: str
    registration_number: str
    vin: Optional[str] = None
    compatible_battery_type: Optional[str] = None

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    registration_number: Optional[str] = None
    is_active: Optional[bool] = None

class VehicleResponse(VehicleBase):
    id: int
    user_id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class VehicleList(BaseModel):
    items: List[VehicleResponse]
