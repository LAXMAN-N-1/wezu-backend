from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Notification(SQLModel, table=True):
    __tablename__ = "notifications"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str
    message: str
    type: str = Field(default="info") # info, alert, promo
    channel: str = Field(default="push") # push, sms, email, whatsapp
    
    payload: Optional[str] = None # JSON data for deeplinking
    scheduled_at: Optional[datetime] = None
    status: str = Field(default="pending") # pending, sent, failed
    
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship()
