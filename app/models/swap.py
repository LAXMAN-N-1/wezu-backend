import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.rental import Rental
    from app.models.battery import Battery
    from app.models.station import Station

class SwapSession(SQLModel, table=True):
    __tablename__ = "swap_sessions"
    __table_args__ = {"schema": "rentals", "extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: Optional[int] = Field(default=None, foreign_key="rentals.rentals.id", index=True)
    user_id: int = Field(foreign_key="core.users.id", index=True)
    station_id: int = Field(foreign_key="stations.stations.id", index=True)
    
    # Battery Details
    old_battery_id: Optional[uuid.UUID] = Field(default=None, foreign_key="inventory.batteries.id")
    new_battery_id: Optional[uuid.UUID] = Field(default=None, foreign_key="inventory.batteries.id")
    
    old_battery_soc: float = Field(default=0.0)
    new_battery_soc: float = Field(default=0.0)
    
    # Metrics
    swap_amount: float = Field(default=0.0)
    currency: str = Field(default="INR")
    
    # Status
    status: str = Field(default="initiated") # initiated, processing, completed, failed
    payment_status: str = Field(default="pending") # pending, paid, failed
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Relationships
    rental: Optional["Rental"] = Relationship(back_populates="swaps")
    user: "User" = Relationship()
    station: "Station" = Relationship()
    old_battery: Optional["Battery"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[SwapSession.old_battery_id]"})
    new_battery: Optional["Battery"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[SwapSession.new_battery_id]"})
