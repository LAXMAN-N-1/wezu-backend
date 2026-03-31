import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class RentalEvent(SQLModel, table=True):
    __tablename__ = "rental_events"
    __table_args__ = {"schema": "rentals", "extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.rentals.id")
    event_type: str # start, stop, swap_request, swap_complete, extend, late_fee
    
    # Details
    description: Optional[str] = None
    station_id: Optional[int] = Field(default=None, foreign_key="stations.stations.id")
    battery_id: Optional[uuid.UUID] = Field(default=None, foreign_key="inventory.batteries.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    rental: "Rental" = Relationship(back_populates="events")
    
# We need to update Rental model to include events relationship
