from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

if TYPE_CHECKING:
    from app.models.user import User

class LoginHistory(SQLModel, table=True):
    __tablename__ = "login_history"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None # City, Country derived from IP
    device_type: str = "unknown" # mobile, web, desktop
    
    status: str = "success" # success, failed
    details: Optional[str] = None # reason for failure if any
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationship
    user: Optional["User"] = Relationship()
