from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class TicketCreate(BaseModel):
    subject: str
    category: str
    description: str # Initial message
    priority: Optional[str] = "medium"

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
    created_at: datetime
    assigned_to: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class TicketMessageCreate(BaseModel):
    message: str
    is_internal_note: bool = False

class TicketMessageResponse(BaseModel):
    id: int
    sender_id: int
    message: str
    created_at: datetime
    is_internal_note: bool
    
    model_config = ConfigDict(from_attributes=True)

class SupportTicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    category: str
    priority: str
    status: str
    created_at: datetime
    assigned_to: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class SupportTicketDetailResponse(SupportTicketResponse):
    messages: List[TicketMessageResponse]

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

# --- Live Chat Schemas ---
class ChatSessionResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    assigned_agent_id: Optional[int] = None

class ChatMessageResponse(BaseModel):
    id: int
    sender_id: int
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


