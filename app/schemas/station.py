from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List
from datetime import datetime

class NearbyFilterSchema(BaseModel):
    price_min: Optional[float] = Field(None, description="Minimum rental price per day")
    price_max: Optional[float] = Field(None, description="Maximum rental price per day")
    min_rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="Minimum station rating")
    battery_type: Optional[str] = Field(None, description="Filter by battery type (e.g., lithium_ion, lfp, lead_acid)")
    capacity_min: Optional[int] = Field(None, description="Minimum battery capacity in mAh")
    capacity_max: Optional[int] = Field(None, description="Maximum battery capacity in mAh")
    availability: Optional[bool] = Field(None, description="Filter only stations with available batteries")

    @model_validator(mode='after')
    def check_price_range(self) -> 'NearbyFilterSchema':
        if self.price_min is not None and self.price_max is not None:
            if self.price_min >= self.price_max:
                raise ValueError("price_min must be strictly less than price_max")
        return self

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

class StationAvailabilityResponse(BaseModel):
    station_id: int
    available_count: int
    batteries: List[dict] # Use dict for now to avoid circular imports if any, or just Any
