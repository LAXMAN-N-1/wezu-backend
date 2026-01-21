from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Address(SQLModel, table=True):
    __tablename__ = "addresses"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str = "India"
    is_default: bool = Field(default=False)
    type: str = "home" # home, work, other
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    user: "User" = Relationship(back_populates="addresses")
