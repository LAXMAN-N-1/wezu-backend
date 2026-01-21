from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StationImageResponse(BaseModel):
    url: str
    is_primary: bool

class StationBase(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    status: str = "active"
    contact_phone: Optional[str] = None
    opening_hours: Optional[str] = None

class StationCreate(StationBase):
    pass

class StationResponse(StationBase):
    id: int
    rating: float
    total_reviews: int
    images: List[StationImageResponse] = []
    
    class Config:
        from_attributes = True

class NearbyStationResponse(StationResponse):
    distance: float # km
    available_batteries: int
