from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class OTP(SQLModel, table=True):
    __tablename__ = "otps"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    target: str = Field(index=True) # Phone or Email
    code: str
    purpose: str = "registration" # login, registration, reset_password
    is_active: bool = Field(default=True)
    is_used: bool = Field(default=False)
    attempts: int = Field(default=0)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
