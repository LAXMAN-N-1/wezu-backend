from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint

class DealerOverviewResponse(BaseModel):
    sales_analytics: Dict[str, Any]
    rental_analytics: Dict[str, Any]
    inventory_analytics: Dict[str, Any]
    revenue_analytics: Dict[str, Any]
    station_analytics: Dict[str, Any]
    customer_analytics: Dict[str, Any]
    promotion_analytics: Dict[str, Any]
    charts: Dict[str, Any] = {}
