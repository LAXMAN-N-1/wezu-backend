from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC, timedelta

if TYPE_CHECKING:
    from app.models.user import User

class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Token Tracking
    token_id: str = Field(index=True) # JTI of the refresh token
    refresh_token_hash: Optional[str] = Field(default=None, index=True)
    
    # Device Info
    device_id: Optional[str] = Field(default=None, index=True)
    device_name: Optional[str] = None
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
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Timestamps
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationship
    user: "User" = Relationship(back_populates="sessions")
