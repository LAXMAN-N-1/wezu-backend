from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Token Tracking
    token_id: str = Field(index=True) # JTI of the refresh token
    
    # Device Info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None # City, Country derived from IP
    device_type: str = "unknown" # mobile, web, desktop
    
    # Status
    is_active: bool = Field(default=True)
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    user: "User" = Relationship(back_populates="sessions")
