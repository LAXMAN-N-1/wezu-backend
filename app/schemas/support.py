from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.support import TicketStatus, TicketPriority

class TicketCreate(BaseModel):
    subject: str
    category: str
    description: str # Initial message
    priority: Optional[str] = "medium"
    attachment_urls: Optional[List[str]] = Field(default=None, max_items=5)

class TicketUpdate(BaseModel):
    subject: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None

class CommentCreate(BaseModel):
    message: str
    is_internal_note: bool = False

class TicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    category: str
    priority: str
    status: str
    attachment_urls: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime
    assigned_to_id: Optional[int] = None
    station_id: Optional[int] = None
    related_to_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class TicketMessageCreate(BaseModel):
    message: str
    is_internal_note: bool = False
    attachment_urls: Optional[List[str]] = Field(default=None, max_items=5)

class TicketMessageResponse(BaseModel):
    id: int
    sender_id: Optional[int] = None
    message: str
    created_at: datetime
    is_internal_note: bool
    attachment_urls: Optional[List[str]] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)

class SupportTicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    category: str
    priority: str
    status: str
    attachment_urls: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime
    assigned_to_id: Optional[int] = None
    station_id: Optional[int] = None
    related_to_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SupportTicketDetailResponse(SupportTicketResponse):
    messages: List[TicketMessageResponse] = []
    customer_history: List[SupportTicketResponse] = []
    related_tickets: List[SupportTicketResponse] = []

# --- Admin & Analytics Schemas ---
class AgentPerformanceResponse(BaseModel):
    agent_id: int
    agent_name: str
    resolved_tickets: int
    avg_resolution_time_hours: float
    csat_score: float

class QueueStatsResponse(BaseModel):
    open_tickets: int
    in_progress: int
    overdue_tickets: int
    priority_breakdown: dict # {"high": 5, "medium": 10, ...}

class CategoryBreakdown(BaseModel):
    category: str
    count: int

class TicketMetricsResponse(BaseModel):
    total_open: int
    avg_resolution_time: float # in hours
    sla_breach_count: int
    csat: float
    category_breakdown: List[CategoryBreakdown]

class TicketRatingUpdate(BaseModel):
    rating: int = Field(ge=1, le=5)

class TicketStatusUpdate(BaseModel):
    status: str

class TicketActionUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    escalate: bool = False
    reason: Optional[str] = None

# --- Live Chat Schemas ---
class ChatSessionResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    assigned_agent_id: Optional[int] = None

class ChatMessageResponse(BaseModel):
    id: int
    sender_id: Optional[int] = None
    message: str
    created_at: datetime

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime
    payload: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


