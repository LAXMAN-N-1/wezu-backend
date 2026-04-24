from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class FeedbackBase(BaseModel):
    rating: int = Field(ge=1, le=5)
    nps_score: Optional[int] = Field(None, ge=0, le=10)
    category: str = "app_experience"
    comment: Optional[str] = None
    metadata: Dict[str, Any] = {}

class FeedbackCreate(FeedbackBase):
    pass

class FeedbackResponse(FeedbackBase):
    id: int
    user_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
