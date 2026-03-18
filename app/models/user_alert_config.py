from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class UserAlertConfig(SQLModel, table=True):
    __tablename__ = "user_alert_config"
    __table_args__ = {"schema": "core"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id", unique=True, index=True)
    
    low_charge_percent: int = Field(default=10)
    low_health_percent: int = Field(default=80)
    high_temp_celsius: int = Field(default=45)
    maintenance_reminder_days: int = Field(default=7)
    
    alerts_enabled: bool = Field(default=True)
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)
