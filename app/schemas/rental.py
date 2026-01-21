from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.battery import BatteryResponse
from app.schemas.station import StationResponse

class RentalBase(BaseModel):
    battery_id: int
    pickup_station_id: int
    duration_days: int = 1

class RentalCreate(RentalBase):
    pass

class RentalEventResponse(BaseModel):
    event_type: str
    created_at: datetime
    description: Optional[str] = None

class RentalResponse(BaseModel):
    id: int
    user_id: int
    battery: BatteryResponse
    pickup_station_id: int
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    total_price: float
    events: List[RentalEventResponse] = []
    
    class Config:
        from_attributes = True

class ActiveRentalResponse(RentalResponse):
    pass
