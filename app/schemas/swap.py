from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class SwapSessionBase(BaseModel):
    station_id: int
    old_battery_serial: Optional[str] = None # User might provide serial or system detects it via slot

class SwapInitRequest(SwapSessionBase):
    pass

class SwapResponse(BaseModel):
    id: int
    status: str
    station_id: int
    station_name: Optional[str] = None
    amount: float
    created_at: datetime
    
    class Config:
        orm_mode = True

class SwapCompleteRequest(BaseModel):
    new_battery_id: int
    new_battery_soc: float
    old_battery_soc: float
