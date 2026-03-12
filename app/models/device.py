from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Device(SQLModel, table=True):
    __tablename__ = "devices"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    fcm_token: str = Field(index=True)
    device_type: str # ios, android, web
    device_id: str # Unique device identifier
    is_active: bool = Field(default=True)
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    user: "User" = Relationship(back_populates="devices")
