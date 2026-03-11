from pydantic import BaseModel, Field
from typing import Optional

class FAQBase(BaseModel):
    question: str = Field(..., description="The FAQ question")
    answer: str = Field(..., description="The FAQ answer")
    category: str = Field(default="general", description="Category of the FAQ")
    is_active: bool = Field(default=True, description="Whether the FAQ is active")

class FAQCreate(FAQBase):
    pass

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
