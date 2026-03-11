from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class BlogBase(SQLModel):
    title: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    content: str
    summary: Optional[str] = None
    featured_image_url: Optional[str] = None
    category: str = Field(index=True)
    author_id: int
    status: str = Field(default="draft", index=True) # draft, published, scheduled
    views_count: int = Field(default=0)
    published_at: Optional[datetime] = None

class Blog(BlogBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
