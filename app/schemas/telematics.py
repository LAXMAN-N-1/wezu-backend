from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel

class TelemeticsDataBase(BaseModel):
    battery_id: int
    timestamp: Optional[datetime] = None # Defaults to now if not provided
    
    # Core Metrics
    voltage: float
    current: float
    temperature: float
    soc: float
    soh: float = 100.0
    
    # GPS Data
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    gps_speed: Optional[float] = None
    
    # Advanced
    error_codes: Optional[Dict[str, Any]] = None
    raw_payload: Optional[Dict[str, Any]] = None

class TelemeticsDataIngest(TelemeticsDataBase):
    pass

class TelemeticsDataResponse(TelemeticsDataBase):
    timestamp: datetime
    received_at: datetime
    
    class Config:
        orm_mode = True

class TelemeticsHistoryResponse(BaseModel):
    items: List[TelemeticsDataResponse]
