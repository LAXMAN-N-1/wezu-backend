from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from sqlalchemy import Column, JSON

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
    assigned_to_id: Optional[int] = Field(default=None, foreign_key="core.users.id")
    station_id: Optional[int] = Field(default=None, foreign_key="stations.stations.id")
    related_to_id: Optional[int] = Field(default=None, foreign_key="core.support_tickets.id")
    
    subject: str
    description: str
    
    status: TicketStatus = Field(default=TicketStatus.OPEN, index=True)
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, index=True)
    
    category: str = Field(default="general") # billing, technical, hardware, other
    
    attachment_urls: List[str] = Field(default=[], sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    # Feedback & CSAT
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    rated_at: Optional[datetime] = None

    # Relationships
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[SupportTicket.user_id]"})
    assignee: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[SupportTicket.assigned_to_id]"})
    messages: List["TicketMessage"] = Relationship(back_populates="ticket")
    
    related_to: Optional["SupportTicket"] = Relationship(
        sa_relationship_kwargs={"remote_side": "SupportTicket.id", "foreign_keys": "[SupportTicket.related_to_id]"}
    )

class TicketMessage(SQLModel, table=True):
    __tablename__ = "ticket_messages"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="core.support_tickets.id", index=True)
    sender_id: Optional[int] = Field(default=None, foreign_key="core.users.id", nullable=True)
    
    message: str
    is_internal_note: bool = Field(default=False)
    attachment_urls: List[str] = Field(default=[], sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    ticket: "SupportTicket" = Relationship(back_populates="messages")
    sender: "User" = Relationship()

class ChatStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    WAITING = "waiting"

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id", index=True)
    assigned_agent_id: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    status: ChatStatus = Field(default=ChatStatus.WAITING)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[ChatSession.user_id]"})
    agent: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[ChatSession.assigned_agent_id]"})
    messages: List["ChatMessage"] = Relationship(back_populates="session")

class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="core.chat_sessions.id", index=True)
    sender_id: Optional[int] = Field(default=None) # None for system/bot
    
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    session: "ChatSession" = Relationship(back_populates="messages")
