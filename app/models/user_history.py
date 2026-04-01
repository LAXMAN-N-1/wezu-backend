from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class UserStatusLog(SQLModel, table=True):
    __tablename__ = "user_status_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    actor_id: int = Field(foreign_key="users.id")
    
    action_type: str = Field(index=True) # role_change, suspension, reactivation
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    
    expires_at: Optional[datetime] = None # For temporary suspensions
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserStatusLog.user_id]"})
    actor: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[UserStatusLog.actor_id]"})
