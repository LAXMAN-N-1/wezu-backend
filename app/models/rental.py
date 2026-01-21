from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Rental(SQLModel, table=True):
    __tablename__ = "rentals"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    battery_id: int = Field(foreign_key="batteries.id")
    pickup_station_id: int = Field(foreign_key="stations.id")
    drop_station_id: Optional[int] = Field(default=None, foreign_key="stations.id")
    
    status: str = Field(default="active") # active, completed, cancelled
    
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    total_price: float = Field(default=0.0)
    
    # Relationships
    user: "User" = Relationship()
    battery: "Battery" = Relationship()
    events: List["RentalEvent"] = Relationship(back_populates="rental")

class Purchase(SQLModel, table=True):
    __tablename__ = "purchases"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    battery_id: int = Field(foreign_key="batteries.id")
    amount: float
    status: str = Field(default="pending") # pending, success, failed
    transaction_id: Optional[int] = Field(default=None, foreign_key="transactions.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship()
    battery: "Battery" = Relationship()
    transaction: Optional["Transaction"] = Relationship()
