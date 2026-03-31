from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, UTC

class StaffProfile(SQLModel, table=True):
    __tablename__ = "staff_profiles"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    
    # Organization Link
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id") # If staff belongs to a dealer
    station_id: Optional[int] = Field(default=None, foreign_key="stations.id") # If assigned to specific station
    
    # Staff Details
    staff_type: str = Field(index=True) # station_manager, technician, warehouse_manager
    employment_id: str = Field(unique=True)
    reporting_manager_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: "User" = Relationship(
        back_populates="staff_profile",
        sa_relationship_kwargs={"foreign_keys": "StaffProfile.user_id"}
    )
    dealer: Optional["DealerProfile"] = Relationship(back_populates="staff_members")
    # station: Optional["Station"] = Relationship()
