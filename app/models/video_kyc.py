from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone; UTC = timezone.utc


if TYPE_CHECKING:
    from app.models.user import User

class VideoKYCSession(SQLModel, table=True):
    __tablename__ = "video_kyc_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    session_id: str = Field(unique=True, index=True) # ID from 3rd party provider
    provider: str = Field(default="unknown")
    status: str = Field(default="initiated") # initiated, completed, failed, rejected, approved
    
    liveness_score: Optional[float] = None
    face_match_score: Optional[float] = None
    
    video_url: Optional[str] = None
    snapshot_url: Optional[str] = None
    
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    
    # Scheduling
    scheduled_at: Optional[datetime] = None
    agent_id: Optional[int] = Field(default=None, foreign_key="users.id")
    agent_notes: Optional[str] = None
    
    # Relationships
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "VideoKYCSession.user_id"})
    # Agent relationship manually handled or added if User model supports it
