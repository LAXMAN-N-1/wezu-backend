from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, field_validator, ConfigDict
from datetime import datetime
from app.models.organization import SocialPlatform

class OrganizationSocialLinkBase(BaseModel):
    platform: SocialPlatform
    url: str

    @field_validator("platform", mode="before")
    @classmethod
    def lowercase_platform(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

class OrganizationSocialLinkCreate(OrganizationSocialLinkBase):
    pass

class OrganizationSocialLinkUpdate(OrganizationSocialLinkBase):
    platform: Optional[SocialPlatform] = None
    url: Optional[str] = None

class OrganizationSocialLinkRead(OrganizationSocialLinkBase):
    id: int
    organization_id: int

    model_config = ConfigDict(from_attributes=True)

class OrganizationBase(BaseModel):
    name: str
    code: str
    website: Optional[str] = None
    is_active: bool = True

class OrganizationCreate(OrganizationBase):
    social_links: Optional[List[OrganizationSocialLinkCreate]] = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None

class OrganizationRead(OrganizationBase):
    id: int
    logo_url: Optional[str] = None
    logo_width: Optional[int] = None
    logo_height: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    social_links: List[OrganizationSocialLinkRead] = []

    model_config = ConfigDict(from_attributes=True)
