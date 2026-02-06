from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime

class FeatureFlag(SQLModel, table=True):
    __tablename__ = "feature_flags"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    is_enabled: bool = Field(default=False)
    rollout_percentage: int = Field(default=100)
    
    # JSON strings for complex targeting
    enabled_for_users: Optional[str] = None 
    enabled_for_tenants: Optional[str] = None
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SystemConfig(SQLModel, table=True):
    __tablename__ = "system_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str
    description: Optional[str] = None
