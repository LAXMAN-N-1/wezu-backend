"""
Support System Models
Chat, tickets, and FAQ management
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ChatSessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

class MessageSender(str, Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    BOT = "BOT"

class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"

class ChatSession(SQLModel, table=True):
    """Chat sessions between customers and support"""
    __tablename__ = "chat_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Session details
    status: str = Field(default="ACTIVE", index=True)
    assigned_agent_id: Optional[int] = Field(None, foreign_key="users.id")
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_message_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Metadata
    customer_satisfaction: Optional[int] = Field(None, ge=1, le=5)  # 1-5 rating
    resolution_time_minutes: Optional[int] = None
    
    # Relationships
    messages: List["ChatMessage"] = Relationship(back_populates="session")

class ChatMessage(SQLModel, table=True):
    """Individual chat messages"""
    __tablename__ = "chat_messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", index=True)
    
    # Message details
    sender_type: str  # CUSTOMER, AGENT, BOT
    sender_id: Optional[int] = Field(None, foreign_key="users.id")
    message: str
    
    # Attachments
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None  # image, document
    
    # Metadata
    is_read: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Relationship
    session: Optional[ChatSession] = Relationship(back_populates="messages")

class SupportTicket(SQLModel, table=True):
    """Support tickets for complex issues"""
    __tablename__ = "support_tickets"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_number: str = Field(unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Ticket details
    subject: str
    description: str
    category: str  # TECHNICAL, BILLING, GENERAL, etc.
    priority: str = Field(default="MEDIUM")
    status: str = Field(default="OPEN", index=True)  # OPEN, IN_PROGRESS, RESOLVED, CLOSED
    
    # Assignment
    assigned_agent_id: Optional[int] = Field(None, foreign_key="users.id")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # SLA
    sla_due_at: Optional[datetime] = None
    is_overdue: bool = Field(default=False)
    
    # Resolution
    resolution_notes: Optional[str] = None
    customer_satisfaction: Optional[int] = Field(None, ge=1, le=5)

class FAQCategory(SQLModel, table=True):
    """FAQ categories"""
    __tablename__ = "faq_categories"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    description: Optional[str] = None
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    
    # Relationships
    items: List["FAQItem"] = Relationship(back_populates="category")

class FAQItem(SQLModel, table=True):
    """FAQ items"""
    __tablename__ = "faq_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="faq_categories.id", index=True)
    
    # Content
    question: str = Field(index=True)
    answer: str
    
    # Metadata
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    view_count: int = Field(default=0)
    helpful_count: int = Field(default=0)
    
    # Search
    tags: Optional[str] = None  # Comma-separated
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    category: Optional[FAQCategory] = Relationship(back_populates="items")

class AutoResponse(SQLModel, table=True):
    """Automated chatbot responses"""
    __tablename__ = "auto_responses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Trigger
    keywords: str  # Comma-separated keywords
    intent: str  # GREETING, PRICING, HOURS, etc.
    
    # Response
    response_text: str
    
    # Metadata
    is_active: bool = Field(default=True)
    usage_count: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
