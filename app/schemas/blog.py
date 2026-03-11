from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class BlogBase(BaseModel):
    title: str
    slug: str
    content: str
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    category: str
    author_id: int
    status: str = "draft"
    published_at: Optional[datetime] = None

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

class BlogPublic(BlogBase):
    id: int
    views_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
