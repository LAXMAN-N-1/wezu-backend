from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.schemas.battery import BatteryResponse
from app.schemas.station import StationResponse

class RentalBase(BaseModel):
    battery_id: int
    pickup_station_id: int
    duration_days: int = 1

class RentalCreate(RentalBase):
    promo_code: Optional[str] = None

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
    
    rental_duration_days: int = 1
    daily_rate: float = 0.0
    damage_deposit: float = 0.0
    discount_amount: float = 0.0
    total_price: float
    
    late_fee_amount: float = 0.0
    is_overdue: bool = False
    
    swap_station_id: Optional[int] = None
    swap_requested_at: Optional[datetime] = None
    
    events: List[RentalEventResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class ActiveRentalResponse(RentalResponse):
    pass

class RentalAnalyticsResponse(BaseModel):
    total_rentals: int
    active_rentals: int
    completed_rentals: int
    avg_duration_hours: float
    total_revenue: float
    rentals_by_station: List[dict] # [{"station_name": "...", "count": 10}, ...]

class LateFeeBreakdown(BaseModel):
    rental_id: int
    hours_late: float
    hourly_rate: float
    chargeable_hours: float
    late_fee_total: float
    status: str # PENDING, PAID, WAIVED

class ReturnResponse(BaseModel):
    rental_id: int
    station_id: int
    status: str # returning
    message: str
    unlock_token: Optional[str] = None
