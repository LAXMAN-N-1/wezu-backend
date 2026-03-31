from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import date, datetime, UTC
import uuid
from sqlalchemy import Column, JSON

if TYPE_CHECKING:
    from app.models.user import User

class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"
    # __table_args__ = {"schema": "public"}

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)

    # Address Details
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    country: str = Field(default="India")

    # Personal Details
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None  # male, female, other, prefer_not_to_say
    preferred_language: str = Field(default="en")
    
    # Notifications
    notification_preferences: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationship
    user: "User" = Relationship(back_populates="user_profile")
