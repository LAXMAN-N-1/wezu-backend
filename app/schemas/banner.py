from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class BannerBase(BaseModel):
    title: str
    image_url: str
    deep_link: Optional[str] = None
    external_url: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class BannerCreate(BannerBase):
    pass

class BannerUpdate(BaseModel):
    title: Optional[str] = None
    image_url: Optional[str] = None
    deep_link: Optional[str] = None
    external_url: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class BannerRead(BannerBase):
    id: int
    click_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
