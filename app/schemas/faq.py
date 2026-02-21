from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class FAQBase(BaseModel):
    question: str
    answer: str
    category: str = "general"
    is_active: bool = True

class FAQCreate(FAQBase):
    pass

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class FAQResponse(FAQBase):
    id: int
    helpful_count: int
    not_helpful_count: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class FAQCategoryResponse(BaseModel):
    category: str
    count: int
