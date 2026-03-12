from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Token Tracking
    token_id: Optional[str] = Field(default=None, index=True) # JTI of the refresh token
    access_token: Optional[str] = Field(default=None, index=True)
    refresh_token: Optional[str] = Field(default=None, index=True)
    
    # Device Info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None # City, Country derived from IP
    device_type: str = "unknown" # mobile, web, desktop
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    
    # Status
    is_active: bool = Field(default=True)
    is_revoked: bool = Field(default=False)
    revoked_at: Optional[datetime] = None
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Timestamps
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    user: "User" = Relationship(back_populates="sessions")
