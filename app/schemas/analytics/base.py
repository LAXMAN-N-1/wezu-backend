from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class KpiCard(BaseModel):
    value: float
    trend_percentage: float
    status: str
    label: Optional[str] = None

class TrendPoint(BaseModel):
    x: str
    y: float

class DistributionPoint(BaseModel):
    label: str
    value: float
    percentage: Optional[float] = None

class GeoIncident(BaseModel):
    lat: float
    lng: float
    type: str
