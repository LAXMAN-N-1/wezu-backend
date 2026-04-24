from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint

class LogisticsOverviewResponse(BaseModel):
    delivery_analytics: Dict[str, Any]
    route_analytics: Dict[str, Any]
    driver_analytics: Dict[str, Any]
    order_analytics: Dict[str, Any]
    reverse_logistics: Dict[str, Any]
    customer_communication: Dict[str, Any]
    customer_feedback: Dict[str, Any]
    charts: Dict[str, Any] = {}
