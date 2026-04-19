from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ReviewBase(BaseModel):
    rating: int
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    station_id: Optional[int] = None
    battery_id: Optional[int] = None

class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    comment: Optional[str] = None

class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    created_at: datetime
    user_name: Optional[str] = None # Populated from user relation
    
    model_config = ConfigDict(from_attributes=True)
