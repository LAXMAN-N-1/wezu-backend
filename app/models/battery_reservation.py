from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class BatteryReservation(SQLModel, table=True):
    __tablename__ = "battery_reservations"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    station_id: int = Field(foreign_key="stations.id")
    battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    
    start_time: datetime = Field(index=True)
    end_time: datetime
    
    status: str = Field(default="PENDING", index=True) # PENDING, ACTIVE, COMPLETED, CANCELLED, EXPIRED
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    # battery: Optional["Battery"] = Relationship() # Assuming relationship in battery.py
