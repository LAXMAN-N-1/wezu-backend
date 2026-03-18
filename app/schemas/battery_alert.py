from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class AlertConfigSchema(BaseModel):
    low_charge_percent: int = 10
    low_health_percent: int = 80
    high_temp_celsius: int = 45
    maintenance_reminder_days: int = 7
    alerts_enabled: bool = True

class BatteryAlertResponse(BaseModel):
    id: int
    battery_id: uuid.UUID
    alert_type: str
    severity: str
    message: str
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
