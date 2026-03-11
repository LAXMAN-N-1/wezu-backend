from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class BookingBase(BaseModel):
    station_id: int

class BookingCreate(BookingBase):
    pass

class BookingUpdate(BaseModel):
    status: Optional[str] = None

class BookingResponse(BookingBase):
    id: int
    user_id: int
    battery_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
