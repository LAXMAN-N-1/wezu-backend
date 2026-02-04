from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

class TelemeticsData(SQLModel, table=True):
    __tablename__ = "telemetics_data"
    
    # TimescaleDB hypertable requirement: timestamp must be part of the primary key
    # or at least the partitioning key. SQLModel/SQLAlchemy handle this via DDL.
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, 
        sa_column=sa.Column(sa.DateTime(timezone=True), primary_key=True)
    )
    battery_id: int = Field(foreign_key="batteries.id", primary_key=True, index=True)
    
    # Core Metrics
    voltage: float = Field(default=0.0)
    current: float = Field(default=0.0)
    temperature: float = Field(default=0.0)
    soc: float = Field(default=0.0) # State of Charge (%)
    soh: float = Field(default=100.0) # State of Health (%)
    
    # GPS Data
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    gps_speed: Optional[float] = None
    
    # Advanced Data
    error_codes: Optional[dict] = Field(default=None, sa_column=sa.Column(JSONB))
    raw_payload: Optional[dict] = Field(default=None, sa_column=sa.Column(JSONB))
    
    # Internal Metadata
    received_at: datetime = Field(default_factory=datetime.utcnow)
