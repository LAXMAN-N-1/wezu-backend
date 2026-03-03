from pydantic import BaseModel
from typing import Optional

class KpiCard(BaseModel):
    value: float
    trend_percentage: float
    status: str

class TrendPoint(BaseModel):
    x: str
    y: float

class GeoIncident(BaseModel):
    lat: float
    lng: float
    type: str
