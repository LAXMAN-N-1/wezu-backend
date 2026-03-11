from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class TransferCreate(BaseModel):
    battery_id: int
    from_location_type: str # warehouse, station, dealer
    from_location_id: int
    to_location_type: str
    to_location_id: int

class TransferResponse(BaseModel):
    id: int
    battery_id: int
    from_location_type: str
    from_location_id: int
    to_location_type: str
    to_location_id: int
    status: str
    manifest_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    id: int
    battery_id: int
    action_type: str
    from_location_type: Optional[str] = None
    from_location_id: Optional[int] = None
    to_location_type: Optional[str] = None
    to_location_id: Optional[int] = None
    actor_id: Optional[int] = None
    notes: Optional[str] = None
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)
