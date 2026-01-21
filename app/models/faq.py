from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class FAQ(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    category: str = "general" # general, rental, payment
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
