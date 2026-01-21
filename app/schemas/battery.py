from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BatteryBase(BaseModel):
    serial_number: str
    model: str
    capacity_ah: float
    
class BatteryCreate(BatteryBase):
    pass

class BatteryHealth(BaseModel):
    health_percentage: float
    cycle_count: int
    temperature: float
    voltage: float
    
class BatteryResponse(BatteryBase):
    id: int
    current_charge: float
    status: str
    health: BatteryHealth
    warranty_expiry: Optional[datetime]
    
    class Config:
        from_attributes = True
