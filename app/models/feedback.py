from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from sqlalchemy import Column, JSON

class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    rating: int = Field(ge=1, le=5) # 1-5 star rating
    nps_score: Optional[int] = Field(default=None, ge=0, le=10) # 0-10 NPS
    
    category: str = Field(default="app_experience") # app_experience, battery_swap, station_quality
    comment: Optional[str] = None
    
    metadata_: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON), alias="metadata")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
