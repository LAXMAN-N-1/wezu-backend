from __future__ import annotations
"""
Alert and monitoring schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Alert ────────────────────────────────────────────────

class AlertCreate(BaseModel):
    alert_type: str
    severity: str = "info"  # info, warning, critical
    title: str
    message: Optional[str] = None
    entity_type: Optional[str] = None  # station, battery, user
    entity_id: Optional[int] = None

class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    is_acknowledged: bool = False
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total_count: int


# ── Station Heartbeat ────────────────────────────────────

class StationHeartbeatResponse(BaseModel):
    id: int
    station_id: int
    status: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    temperature: Optional[float] = None
    uptime_seconds: Optional[int] = None
    error_count: int = 0
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Telemetry ────────────────────────────────────────────

class TelemetryResponse(BaseModel):
    id: int
    battery_id: int
    voltage: Optional[float] = None
    current: Optional[float] = None
    temperature: Optional[float] = None
    soc: Optional[float] = None
    soh: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TelemetryListResponse(BaseModel):
    readings: List[TelemetryResponse]
    total_count: int
