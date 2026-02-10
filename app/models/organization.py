from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SocialPlatform(str, Enum):
    website = "website"
    facebook = "facebook"
    instagram = "instagram"
    linkedin = "linkedin"
    twitter = "twitter"
    youtube = "youtube"
    others = "others"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None

class OrganizationSocialLink(SQLModel, table=True):
    __tablename__ = "organization_social_links"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id")
    platform: SocialPlatform
    url: str
    
    # Relationship
    organization: "Organization" = Relationship(back_populates="social_links")

class Organization(SQLModel, table=True):
    __tablename__ = "organizations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    code: str = Field(unique=True, index=True)
    website: Optional[str] = None
    
    # Logo support
    logo_url: Optional[str] = None
    logo_width: Optional[int] = None
    logo_height: Optional[int] = None
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    social_links: List[OrganizationSocialLink] = Relationship(
        back_populates="organization",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    branches: List["Branch"] = Relationship(
        back_populates="organization",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
