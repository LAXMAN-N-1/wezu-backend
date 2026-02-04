from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class TicketCreate(BaseModel):
    subject: str
    category: str
    description: str # Initial message
    priority: Optional[str] = "medium"

class TicketMessageCreate(BaseModel):
    message: str
    is_internal_note: bool = False

class TicketMessageResponse(BaseModel):
    id: int
    sender_id: int
    message: str
    created_at: datetime
    is_internal_note: bool
    
    class Config:
        orm_mode = True

class SupportTicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    category: str
    priority: str
    status: str
    created_at: datetime
    assigned_to_id: Optional[int] = None
    
    class Config:
        orm_mode = True

class SupportTicketDetailResponse(SupportTicketResponse):
    messages: List[TicketMessageResponse]

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime
    payload: Optional[str] = None
    
    class Config:
        orm_mode = True


