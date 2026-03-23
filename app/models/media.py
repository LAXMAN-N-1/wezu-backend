from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class MediaAsset(SQLModel, table=True):
    __tablename__ = "media_assets"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_type: str # image/png, image/jpeg, application/pdf
    file_size_bytes: int
    url: str
    
    # Metadata
    alt_text: Optional[str] = None
    category: str = Field(default="general") # blog, banner, kyc, profile
    
    uploaded_by_id: int
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
