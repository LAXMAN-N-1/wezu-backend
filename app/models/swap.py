from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.rental import Rental
    from app.models.battery import Battery
    from app.models.station import Station

class Swap(SQLModel, table=True):
    __tablename__ = "swaps"
    __table_args__ = {"schema": "rentals"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.rentals.id", index=True)
    user_id: int = Field(foreign_key="core.users.id", index=True)
    station_id: int = Field(foreign_key="stations.stations.id", index=True)
    
    # Battery Details
    old_battery_id: int = Field(foreign_key="inventory.batteries.id")
    new_battery_id: int = Field(foreign_key="inventory.batteries.id")
    
    # Metrics
    old_battery_charge: float = Field(default=0.0)
    new_battery_charge: float = Field(default=100.0)
    swap_amount: float = Field(default=0.0)
    currency: str = Field(default="INR")
    
    # Status
    status: str = Field(default="completed") # processing, completed, failed
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    rental: "Rental" = Relationship(back_populates="swaps")
    user: "User" = Relationship()
    station: "Station" = Relationship()
    old_battery: "Battery" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Swap.old_battery_id]"})
    new_battery: "Battery" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Swap.new_battery_id]"})
