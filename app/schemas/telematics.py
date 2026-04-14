from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class TelematicsDataBase(BaseModel):
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

class TelematicsDataIngest(TelematicsDataBase):
    pass

class TelematicsDataResponse(TelematicsDataBase):
    timestamp: datetime
    received_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TelematicsHistoryResponse(BaseModel):
    items: List[TelematicsDataResponse]

# Backward-compat aliases (hardened repo used this spelling)
TelemeticsDataIngest = TelematicsDataIngest
TelemeticsDataResponse = TelematicsDataResponse
