from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ManifestItemCreate(BaseModel):
    battery_id: str
    type: str
    status: str = "pending"

class ManifestItemRead(BaseModel):
    id: int
    battery_id: str
    type: str
    status: str
    
    class Config:
        from_attributes = True

class ManifestCreate(BaseModel):
    id: str
    source: str
    date: datetime
    status: str = "In Transit"
    items: List[ManifestItemCreate]

class ManifestRead(BaseModel):
    id: str
    source: str
    date: datetime
    status: str
    created_at: datetime
    items: List[ManifestItemRead] = []

    class Config:
        from_attributes = True

class ManifestItemUpdate(BaseModel):
    battery_id: str
    status: str
    damage_report: Optional[str] = None
    damage_photo_path: Optional[str] = None

class ManifestReceiveRequest(BaseModel):
    warehouse_id: Optional[int] = None
    items: List[ManifestItemUpdate]
