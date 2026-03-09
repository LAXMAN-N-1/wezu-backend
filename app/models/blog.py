from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime

class Blog(SQLModel, table=True):
    __tablename__ = "blogs"
    __table_args__ = {"schema": "core"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    slug: str = Field(index=True, unique=True)
    content: str
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    category: str = Field(default="news") # news, educational, update
    
    author_id: int
    status: str = Field(default="draft") # draft, published, archived
    
    views_count: int = Field(default=0)
    
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
