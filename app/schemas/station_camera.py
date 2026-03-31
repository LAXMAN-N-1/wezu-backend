from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StationCameraBase(BaseModel):
    name: str
    rtsp_url: str
    status: Optional[str] = "active"

class StationCameraCreate(StationCameraBase):
    pass

class StationCameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    status: Optional[str] = None

class StationCameraResponse(StationCameraBase):
    id: int
    station_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
