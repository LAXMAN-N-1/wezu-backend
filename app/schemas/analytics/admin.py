from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint, GeoIncident

class AdminOverviewResponse(BaseModel):
    overview: Dict[str, KpiCard]
    financials: Dict[str, List[TrendPoint]]
    risk: Dict[str, Any]
