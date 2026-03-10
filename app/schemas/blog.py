from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class BlogBase(BaseModel):
    title: str
    slug: str
    content: str
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    category: str = "news"
    status: str = "draft"

class BlogCreate(BlogBase):
    pass

class BlogUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    published_at: Optional[datetime] = None

class BlogRead(BlogBase):
    id: int
    author_id: int
    views_count: int
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
