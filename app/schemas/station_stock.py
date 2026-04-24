from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime

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
    id: int
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


class DealerStockRequestResponse(BaseModel):
    id: int
    dealer_id: int
    dealer_name: Optional[str] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    quantity: int
    priority: str
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    admin_notes: Optional[str] = None
    rejected_reason: Optional[str] = None
    delivery_date: Optional[datetime] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    fulfilled_quantity: Optional[int] = None


class DealerStockRequestReview(BaseModel):
    action: Literal["approve", "reject"]
    admin_notes: Optional[str] = None
    rejected_reason: Optional[str] = None


class DealerStockRequestFulfillRequest(BaseModel):
    warehouse_id: Optional[int] = None
    assigned_driver_id: Optional[int] = None
    fulfilled_quantity: Optional[int] = None
    admin_notes: Optional[str] = None


class DealerStockRequestFulfillResponse(BaseModel):
    request_id: int
    status: str
    fulfilled_quantity: int
    logistics_order_id: str
