from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class LegalDocumentBase(BaseModel):
    title: str
    slug: str
    content: str
    version: str = "1.0.0"
    is_active: bool = True
    force_update: bool = False

class LegalDocumentCreate(LegalDocumentBase):
    pass

class LegalDocumentUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    force_update: Optional[bool] = None
    published_at: Optional[datetime] = None

class LegalDocumentRead(LegalDocumentBase):
    id: int
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
