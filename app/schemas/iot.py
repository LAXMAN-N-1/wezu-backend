from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class IoTDeviceResponse(BaseModel):
    id: int
    device_id: str
    device_type: str
    status: str
    last_heartbeat: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
