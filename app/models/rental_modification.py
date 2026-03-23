from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class RentalExtension(SQLModel, table=True):
    __tablename__ = "rental_extensions"
    # __table_args__ = {"schema": "public"}
    """Extension requests for active rentals"""
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id")
    user_id: int = Field(foreign_key="users.id")
    
    current_end_date: datetime
    requested_end_date: datetime
    extension_days: int
    
    status: str = Field(default="PENDING")  # PENDING, APPROVED, REJECTED, CANCELLED
    
    additional_cost: float = Field(default=0.0)
    payment_status: str = Field(default="PENDING")  # PENDING, PAID, FAILED
    payment_transaction_id: Optional[int] = Field(default=None, foreign_key="payment_transactions.id")
    
    reason: Optional[str] = None
    admin_notes: Optional[str] = None
    
    approved_by: Optional[int] = Field(default=None, foreign_key="users.id")
    approved_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    rental: "Rental" = Relationship()
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[RentalExtension.user_id]"})
    approver: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[RentalExtension.approved_by]"})

class RentalPause(SQLModel, table=True):
    __tablename__ = "rental_pauses"
    # __table_args__ = {"schema": "public"}
    """Temporary rental pausing (e.g., user traveling)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id")
    user_id: int = Field(foreign_key="users.id")
    
    pause_start_date: datetime
    pause_end_date: datetime
    pause_days: int
    
    status: str = Field(default="PENDING")  # PENDING, APPROVED, ACTIVE, COMPLETED, REJECTED, CANCELLED
    
    reason: str
    
    # Pause may have reduced or waived charges
    daily_pause_charge: float = Field(default=0.0)  # Reduced rate during pause
    total_pause_cost: float = Field(default=0.0)
    
    # Battery must be returned to station during pause
    battery_returned_to_station_id: Optional[int] = Field(default=None, foreign_key="stations.id")
    battery_returned_at: Optional[datetime] = None
    battery_reclaimed_at: Optional[datetime] = None
    
    admin_notes: Optional[str] = None
    approved_by: Optional[int] = Field(default=None, foreign_key="users.id")
    approved_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    rental: "Rental" = Relationship()
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[RentalPause.user_id]"})
    approver: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[RentalPause.approved_by]"})
    station: Optional["Station"] = Relationship()
