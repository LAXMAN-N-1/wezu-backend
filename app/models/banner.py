from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Banner(SQLModel, table=True):
    __tablename__ = "banners"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    image_url: str
    deep_link: Optional[str] = None # e.g. wezu://stations/123
    external_url: Optional[str] = None
    
    priority: int = Field(default=0)
    is_active: bool = Field(default=True)
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    click_count: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
