from pydantic import BaseModel
from typing import Dict, List, Any
from .base import KpiCard, TrendPoint, GeoIncident

class AdminOverviewResponse(BaseModel):
    platform_overview: Dict[str, KpiCard]
    rental_analytics: Dict[str, Any]
    revenue_analytics: Dict[str, Any]
    battery_fleet_analytics: Dict[str, Any]
    station_analytics: Dict[str, Any]
    customer_analytics: Dict[str, Any]
    financial_analytics: Dict[str, Any]
    operational_analytics: Dict[str, Any]
    charts: Dict[str, Any] = {}
