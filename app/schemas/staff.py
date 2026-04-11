"""
Staff profile schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class StaffProfileCreate(BaseModel):
    user_id: int
    staff_type: str  # station_manager, technician, field_officer
    employment_id: Optional[str] = None
    station_id: Optional[int] = None
    dealer_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None

class StaffProfileUpdate(BaseModel):
    staff_type: Optional[str] = None
    employment_id: Optional[str] = None
    station_id: Optional[int] = None
    dealer_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None
    is_active: Optional[bool] = None

class StaffProfileResponse(BaseModel):
    id: int
    user_id: int
    staff_type: str
    employment_id: Optional[str] = None
    station_id: Optional[int] = None
    dealer_id: Optional[int] = None
    reporting_manager_id: Optional[int] = None
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
