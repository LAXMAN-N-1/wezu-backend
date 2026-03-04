from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint

class CustomerOverviewResponse(BaseModel):
    personal_overview: Dict[str, Any]
    spending_analytics: Dict[str, Any]
    usage_analytics: Dict[str, Any]
    battery_analytics: Dict[str, Any]
    environmental_impact: Dict[str, Any]
    rental_history: List[Dict[str, Any]]
    charts: Dict[str, Any] = {}
