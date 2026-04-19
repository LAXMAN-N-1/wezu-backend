from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone; UTC = timezone.utc
from sqlmodel import SQLModel, Field, Relationship
from app.models.user import User

class Vehicle(SQLModel, table=True):
    __tablename__ = "vehicles"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Vehicle Details
    make: str # e.g., Ather, Ola
    model: str # e.g., 450X, S1 Pro
    registration_number: str = Field(unique=True, index=True)
    vin: Optional[str] = None # Chassis Number
    
    # Battery Compatibility
    compatible_battery_type: Optional[str] = None # 60V, 72V etc.
    
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: User = Relationship(back_populates="vehicles")
