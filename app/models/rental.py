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
    
    # Cost Breakdown
    rental_duration_days: int = Field(default=1)
    daily_rate: float = Field(default=0.0)
    damage_deposit: float = Field(default=0.0)
    discount_amount: float = Field(default=0.0)
    promo_code_id: Optional[int] = Field(default=None, foreign_key="promo_codes.id")
    
    total_price: float = Field(default=0.0)
    late_fee_amount: float = Field(default=0.0)
    late_fee_applicable: bool = Field(default=False)
    
    # Verification & Flow
    terms_accepted_at: Optional[datetime] = None
    pickup_verified: bool = Field(default=False)
    return_verified: bool = Field(default=False)
    
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
