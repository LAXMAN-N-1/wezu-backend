from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    from app.models.user import User

class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SupportTicket(SQLModel, table=True):
    __tablename__ = "support_tickets"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    user_id: int = Field(foreign_key="core.users.id", index=True)
    assigned_to: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    subject: str
    description: str
    
    status: TicketStatus = Field(default=TicketStatus.OPEN, index=True)
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, index=True)
    
    category: str = Field(default="general") # billing, technical, hardware, other
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    # Relationships
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[SupportTicket.user_id]"})
    assignee: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[SupportTicket.assigned_to]"})
