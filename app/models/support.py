from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.models.user import User

class SupportTicket(SQLModel, table=True):
    __tablename__ = "support_tickets"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Creator
    user_id: int = Field(foreign_key="users.id")
    
    # Details
    subject: str
    category: str = Field(index=True) # technical, billing, account, other
    priority: str = Field(default="medium") # low, medium, high, critical
    status: str = Field(default="open") # open, in_progress, resolved, closed
    
    # Assigned Admin (for future use)
    assigned_to_id: Optional[int] = None 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship()
    messages: List["TicketMessage"] = Relationship(back_populates="ticket")

class TicketMessage(SQLModel, table=True):
    __tablename__ = "ticket_messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="support_tickets.id")
    
    sender_id: int = Field(foreign_key="users.id") # Can be customer or admin
    message: str
    
    is_internal_note: bool = Field(default=False) # For admin only notes
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    ticket: SupportTicket = Relationship(back_populates="messages")
    sender: User = Relationship()
