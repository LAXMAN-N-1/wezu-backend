from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint

class DealerOverviewResponse(BaseModel):
    overview: Dict[str, KpiCard]
    inventory: Dict[str, Any]
    sales: Dict[str, List[TrendPoint]]
    operations: Dict[str, Any] = {}
