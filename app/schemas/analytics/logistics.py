from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint

class LogisticsOverviewResponse(BaseModel):
    overview: Dict[str, KpiCard]
    slas: Dict[str, List[TrendPoint]]
    network_map: Dict[str, Any]
