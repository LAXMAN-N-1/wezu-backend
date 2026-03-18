import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class ChargingQueue(SQLModel, table=True):
    __tablename__ = "charging_queue"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    battery_id: int = Field(foreign_key="batteries.id")
    
    priority_score: float = Field(default=0.0)
    queue_position: int
    estimated_completion_time: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    # battery: "Battery" = Relationship()
