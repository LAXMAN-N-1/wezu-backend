from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
import uuid

# --- Stock Overview ---
class StockOverviewResponse(BaseModel):
    total_batteries: int
    total_stations: int
    avg_utilization: float
    low_stock_alerts: int
    warehouse_count: int
    service_count: int
    available_count: int
    rented_count: int
    maintenance_count: int

class LocationStockResponse(BaseModel):
    location_name: str
    location_type: str
    available_count: int
    rented_count: int
    maintenance_count: int
    total_assigned: int
    utilization_percentage: float

# --- Station Stock ---
class StationStockConfigResponse(BaseModel):
    max_capacity: int
    reorder_point: int
    reorder_quantity: int
    manager_email: Optional[str] = None
    manager_phone: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class StationStockResponse(BaseModel):
    station_id: int
    station_name: str
    address: str
    latitude: float
    longitude: float
    available_count: int
    rented_count: int
    maintenance_count: int
    total_assigned: int
    utilization_percentage: float
    is_low_stock: bool
    config: Optional[StationStockConfigResponse] = None

# --- Forecast ---
class StockForecastResponse(BaseModel):
    avg_rentals_per_day: float
    projected_demand_30d: int
    recommended_reorder: int
    recommended_date: Optional[datetime]
    predicted_stockout_days: Optional[int]

class StationStockDetailResponse(BaseModel):
    station: StationStockResponse
    forecast: StockForecastResponse
    batteries: List[dict] # Will contain serialized batteries
    utilization_trend: List[float] = [] # Mapped 7-day trend

# --- Reorder / Config Updates ---
class StationStockConfigUpdate(BaseModel):
    max_capacity: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_quantity: Optional[int] = None
    manager_email: Optional[str] = None
    manager_phone: Optional[str] = None

class ReorderRequestCreate(BaseModel):
    station_id: int
    requested_quantity: int
    reason: Optional[str] = None

class ReorderRequestResponse(BaseModel):
    id: uuid.UUID
    station_id: int
    requested_quantity: int
    reason: Optional[str] = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Alerts ---
class StockAlertResponse(BaseModel):
    station_id: int
    station_name: str
    current_count: int
    capacity: int
    threshold: int
    utilization_percentage: float
