from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class LegalDocument(SQLModel, table=True):
    __tablename__ = "legal_documents"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    slug: str = Field(index=True, unique=True) # terms-of-service, privacy-policy
    content: str
    version: str = Field(default="1.0.0")
    
    is_active: bool = Field(default=True)
    force_update: bool = Field(default=False) # If true, users must re-accept
    
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
