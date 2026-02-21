from pydantic import BaseModel, ConfigDict
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
    contact_email: Optional[str] = None
    opening_hours: Optional[str] = None
    is_24x7: bool = False
    amenities: Optional[str] = None
    
    # New Operational Fields
    station_type: str = "automated"
    total_slots: int = 0
    power_rating_kw: Optional[float] = None
    
    # Ownership/Location
    zone_id: Optional[int] = None
    dealer_id: Optional[int] = None

class StationCreate(StationBase):
    pass

class StationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    is_24x7: Optional[bool] = None
    amenities: Optional[str] = None
    total_slots: Optional[int] = None
    power_rating_kw: Optional[float] = None

class StationResponse(StationBase):
    id: int
    rating: float
    total_reviews: int
    available_batteries: int = 0
    available_slots: int = 0
    images: List[StationImageResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class NearbyStationResponse(StationResponse):
    distance: float # km
    # available_batteries is already in StationResponse now

class StationPerformanceResponse(BaseModel):
    daily_rentals: int
    daily_revenue: float
    avg_duration_minutes: float
    satisfaction_score: float
    utilization_percentage: float

class StationMapResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    status: str
    available_batteries: int

class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    intensity: float # 0.0 to 1.0 based on demand
