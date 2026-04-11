from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, UTC

class FAQ(SQLModel, table=True):
    __tablename__ = "faqs"
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    category: str = Field(default="general") # general, rental, payment
    is_active: bool = Field(default=True)
    
    helpful_count: int = Field(default=0)
    not_helpful_count: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
