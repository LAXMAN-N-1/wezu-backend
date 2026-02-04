from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery

class SwapSession(SQLModel, table=True):
    __tablename__ = "swap_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Actors
    user_id: int = Field(foreign_key="users.id")
    station_id: int = Field(foreign_key="stations.id")
    
    # Battery In (Returned)
    old_battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    old_battery_soc: Optional[float] = None # State of Charge when returned
    return_slot_id: Optional[int] = None # StationSlot ID
    
    # Battery Out (Taken)
    new_battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    new_battery_soc: Optional[float] = None # SoC when taken (usually 100%)
    dispense_slot_id: Optional[int] = None # StationSlot ID
    
    # Financials
    amount: float = Field(default=0.0)
    currency: str = Field(default="INR")
    payment_status: str = Field(default="pending") # pending, paid, failed
    
    # Operational Status
    status: str = Field(default="initiated") # initiated, battery_returned, battery_dispensed, completed, failed
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Relationships
    user: User = Relationship()
    station: Station = Relationship()
    # old_battery: Optional[Battery] = Relationship(sa_relationship_kwargs={"foreign_keys": "SwapSession.old_battery_id"})
    # new_battery: Optional[Battery] = Relationship(sa_relationship_kwargs={"foreign_keys": "SwapSession.new_battery_id"})
