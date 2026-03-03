from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint

class CustomerOverviewResponse(BaseModel):
    ride_status: Dict[str, Any]
    gamification: Dict[str, Any]
    savings: Dict[str, KpiCard]
