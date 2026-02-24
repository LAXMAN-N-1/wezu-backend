from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.battery import Battery
    from app.models.station import Station
    from app.models.swap import Swap
    from app.models.finance.transaction import Transaction

class RentalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    PENDING_PAYMENT = "pending_payment"

class Rental(SQLModel, table=True):
    __tablename__ = "rentals"
    __table_args__ = {"schema": "rentals"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Core References
    user_id: int = Field(foreign_key="core.users.id", index=True)
    battery_id: int = Field(foreign_key="inventory.batteries.id", index=True)
    
    # Location
    start_station_id: int = Field(foreign_key="stations.stations.id")
    end_station_id: Optional[int] = Field(default=None, foreign_key="stations.stations.id")
    
    # Timings
    start_time: datetime = Field(default_factory=datetime.utcnow)
    expected_end_time: datetime
    end_time: Optional[datetime] = None
    
    # Financials
    total_amount: float = Field(default=0.0)
    security_deposit: float = Field(default=0.0)
    late_fee: float = Field(default=0.0)
    currency: str = Field(default="INR")
    is_deposit_refunded: bool = Field(default=False)
    
    # State
    status: RentalStatus = Field(default=RentalStatus.ACTIVE, index=True)
    
    # Metrics
    start_battery_level: float = Field(default=100.0)
    end_battery_level: float = Field(default=0.0)
    distance_traveled_km: float = Field(default=0.0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship(back_populates="rentals")
    battery: "Battery" = Relationship(back_populates="rentals")
    start_station: "Station" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Rental.start_station_id]"})
    end_station: Optional["Station"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Rental.end_station_id]"})
    
    swaps: List["Swap"] = Relationship(back_populates="rental")
    transactions: List["Transaction"] = Relationship(back_populates="rental")

class Purchase(SQLModel, table=True):
    __tablename__ = "purchases"
    __table_args__ = {"schema": "rentals"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id", index=True)
    battery_id: int = Field(foreign_key="inventory.batteries.id", index=True)
    amount: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

