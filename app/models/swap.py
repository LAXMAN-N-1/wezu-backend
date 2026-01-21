from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class SwapRequest(SQLModel, table=True):
    __tablename__ = "swap_requests"
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id")
    station_id: int = Field(foreign_key="stations.id")
    reserved_battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    
    status: str = Field(default="REQUESTED") # REQUESTED, RESERVED, COMPLETED, EXPIRED, CANCELLED
    
    expiry_time: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Relationships
    rental: "Rental" = Relationship()
    station: "Station" = Relationship()
    reserved_battery: Optional["Battery"] = Relationship()

class SwapHistory(SQLModel, table=True):
    __tablename__ = "swap_histories"
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id")
    station_id: int = Field(foreign_key="stations.id")
    
    old_battery_id: int = Field(foreign_key="batteries.id") # Returned
    new_battery_id: int = Field(foreign_key="batteries.id") # Taken
    
    soc_in: float # Charge level of returned battery
    soc_out: float # Charge level of new battery
    
    swap_fee: float = Field(default=0.0)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
