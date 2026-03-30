from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User
from datetime import datetime, UTC

class Address(SQLModel, table=True):
    __tablename__ = "addresses"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    street_address: Optional[str] = None # Deprecated, kept for backward compatibility if needed, else remove
    city: str
    state: str
    postal_code: str
    country: str = "India"
    is_default: bool = Field(default=False)
    type: str = "home" # home, work, other
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationship
    user: "User" = Relationship(back_populates="addresses")
