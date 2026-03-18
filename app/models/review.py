import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    station_id: Optional[int] = Field(default=None, foreign_key="stations.id")
    battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    rental_id: Optional[int] = Field(default=None, foreign_key="rentals.id")
    
    rating: int = Field(default=5) # 1-5
    comment: Optional[str] = None
    response_from_station: Optional[str] = None
    
    is_verified_rental: bool = Field(default=False)
    is_hidden: bool = Field(default=False)
    helpful_count: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship()
    station: Optional["Station"] = Relationship(back_populates="reviews")
