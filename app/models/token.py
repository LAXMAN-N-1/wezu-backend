from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class SessionToken(SQLModel, table=True):
    __tablename__ = "session_tokens"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    access_token: str = Field(index=True)
    refresh_token: str = Field(index=True)
    
    # Device Info
    device_id: Optional[str] = None
    device_type: Optional[str] = None # iOS, Android, Web
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    ip_address: Optional[str] = None
    
    # Status
    is_active: bool = Field(default=True)
    is_revoked: bool = Field(default=False)
    revoked_at: Optional[datetime] = None
    
    # Timestamps
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    user: "User" = Relationship(back_populates="sessions")
