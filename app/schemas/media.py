from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class MediaAssetBase(BaseModel):
    file_name: str
    file_type: str
    file_size_bytes: int
    url: str
    alt_text: Optional[str] = None
    category: str = "general"

class MediaAssetCreate(MediaAssetBase):
    pass

class MediaAssetUpdate(BaseModel):
    alt_text: Optional[str] = None
    category: Optional[str] = None

class MediaAssetRead(MediaAssetBase):
    id: int
    uploaded_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
