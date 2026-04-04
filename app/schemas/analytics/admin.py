from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field

from .base import KpiCard

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


class AdminDashboardBootstrapResponse(BaseModel):
    period: str
    generated_at: datetime
    overview: Dict[str, Any] = Field(default_factory=dict)
    trends: Dict[str, Any] = Field(default_factory=dict)
    conversion_funnel: Dict[str, Any] = Field(default_factory=dict)
    battery_health_distribution: Dict[str, Any] = Field(default_factory=dict)
    inventory_status: Dict[str, Any] = Field(default_factory=dict)
    demand_forecast: Dict[str, Any] = Field(default_factory=dict)
    revenue_by_station: Dict[str, Any] = Field(default_factory=dict)
    recent_activity: Dict[str, Any] = Field(default_factory=dict)
    top_stations: Dict[str, Any] = Field(default_factory=dict)
