from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class SupportTicketCreate(BaseModel):
    subject: str
    detail: str # Initial message
    priority: str = "medium"

class SupportMessageCreate(BaseModel):
    detail: str

class SupportMessageResponse(BaseModel):
    id: int
    sender_id: int
    detail: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class SupportTicketResponse(BaseModel):
    id: int
    subject: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
