from __future__ import annotations
"""
Pydantic schemas for the Dealer Portal Inventory screen endpoints.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ──────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────

class BatteryStatusEnum(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    RENTED = "rented"
    MAINTENANCE = "maintenance"
    CHARGING = "charging"
    RETIRED = "retired"


class HealthCondition(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


# ──────────────────────────────────────────────────
# Request Schemas
# ──────────────────────────────────────────────────

class BatteryStatusUpdateRequest(BaseModel):
    """POST /dealers/{dealerId}/batteries/{batteryId}/status"""
    status: str
    reason: Optional[str] = None
    estimated_return_date: Optional[datetime] = None
    notes: Optional[str] = None


class BatteryCreateRequest(BaseModel):
    """POST /dealers/{dealerId}/batteries"""
    serial_number: str
    model_id: Optional[int] = None
    station_id: int
    purchase_price: float = 0.0
    purchase_date: Optional[str] = None
    warranty_expiry: Optional[str] = None
    iot_device_id: Optional[str] = None
    battery_type: Optional[str] = "48V/30Ah"
    notes: Optional[str] = None
    model_config = ConfigDict(protected_namespaces=())


class BulkStatusUpdateRequest(BaseModel):
    """POST /dealers/{dealerId}/batteries/bulk-status"""
    battery_ids: List[int]
    status: str
    reason: Optional[str] = None
    estimated_return_date: Optional[datetime] = None


class StockRequestCreate(BaseModel):
    """POST /dealers/{dealerId}/stock-requests"""
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    quantity: int = Field(ge=1)
    delivery_date: Optional[str] = None
    priority: str = "normal"
    reason: Optional[str] = None
    notes: Optional[str] = None
    model_config = ConfigDict(protected_namespaces=())


# ──────────────────────────────────────────────────
# Response Schemas — Metrics
# ──────────────────────────────────────────────────

class TrendInfo(BaseModel):
    value: int = 0
    change: int = 0
    percentage: float = 0.0
    direction: str = "stable"
    period: str = "week"


class HealthDistributionItem(BaseModel):
    count: int = 0
    percentage: float = 0.0


class HealthInfo(BaseModel):
    average: float = 0.0
    distribution: Dict[str, HealthDistributionItem] = {}
    trend: float = 0.0


class UtilizationInfo(BaseModel):
    rate: float = 0.0
    target: float = 75.0
    status: str = "good"
    trend: float = 0.0


class InventoryMetricsResponse(BaseModel):
    """GET /dealers/{dealerId}/inventory/metrics"""
    success: bool = True
    data: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────
# Response Schemas — Battery List
# ──────────────────────────────────────────────────

class BatteryHealthResponse(BaseModel):
    percentage: float = 100.0
    cycles: int = 0
    condition: str = "excellent"
    last_test_date: Optional[str] = None


class BatteryChargeResponse(BaseModel):
    percentage: float = 100.0
    last_charge_time: Optional[str] = None


class BatteryLocationResponse(BaseModel):
    station_id: Optional[int] = None
    station_name: str = ""


class BatteryValueResponse(BaseModel):
    purchase_price: float = 0.0
    current_value: float = 0.0


class BatteryItemResponse(BaseModel):
    battery_id: int
    serial_number: str
    model_id: Optional[int] = None
    model_name: str = ""
    health: BatteryHealthResponse
    current_status: str
    location: BatteryLocationResponse
    charge: BatteryChargeResponse
    value: BatteryValueResponse
    battery_type: Optional[str] = None
    cycle_count: int = 0
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class PaginationResponse(BaseModel):
    page: int = 1
    limit: int = 50
    total: int = 0
    total_pages: int = 0
    has_next_page: bool = False
    has_prev_page: bool = False


class InventorySummaryResponse(BaseModel):
    total_stock: int = 0
    available: int = 0
    reserved: int = 0
    rented: int = 0
    maintenance: int = 0
    charging: int = 0
    damaged: int = 0
    total_value: float = 0.0
    average_health: float = 0.0
    last_updated: Optional[str] = None


class InventoryListResponse(BaseModel):
    """GET /dealers/{dealerId}/inventory"""
    success: bool = True
    data: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────
# Response Schemas — Health Analytics
# ──────────────────────────────────────────────────

class AlertItem(BaseModel):
    alert_id: str = ""
    type: str = ""
    count: int = 0
    severity: str = "medium"
    message: str = ""
    action: str = ""


class RecommendationItem(BaseModel):
    priority: str = "medium"
    action: str = ""
    expected_impact: str = ""
    estimated_cost: float = 0.0


class HealthAnalyticsResponse(BaseModel):
    """GET /dealers/{dealerId}/inventory/health-analytics"""
    success: bool = True
    data: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────
# Response Schemas — Models
# ──────────────────────────────────────────────────

class ModelInventoryInfo(BaseModel):
    total: int = 0
    available: int = 0
    reserved: int = 0
    maintenance: int = 0
    damaged: int = 0


class ModelHealthInfo(BaseModel):
    average: float = 0.0
    distribution: Dict[str, int] = {}


class ModelValueInfo(BaseModel):
    cost_per_unit: float = 0.0
    total_inventory_value: float = 0.0


class ModelDemandInfo(BaseModel):
    daily_average: float = 0.0
    weekly_total: int = 0
    monthly_total: int = 0


class ModelForecastInfo(BaseModel):
    next_7_days: int = 0
    next_30_days: int = 0
    confidence: float = 0.0


class ModelReorderInfo(BaseModel):
    threshold: int = 50
    recommended: int = 75
    is_low: bool = False


class InventoryModelsResponse(BaseModel):
    """GET /dealers/{dealerId}/inventory/models"""
    success: bool = True
    data: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────
# Response Schemas — Status Change
# ──────────────────────────────────────────────────

class StatusChangeResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Dict[str, Any] = {}


class BulkStatusChangeResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Dict[str, Any] = {}


# ──────────────────────────────────────────────────
# Response Schemas — Stock Request
# ──────────────────────────────────────────────────

class StockRequestResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Dict[str, Any] = {}


# ──────────────────────────────────────────────────
# Response Schemas — Trends
# ──────────────────────────────────────────────────

class TrendDataPoint(BaseModel):
    date: str
    total_stock: int = 0
    available: int = 0
    reserved: int = 0
    maintenance: int = 0
    damaged: int = 0


class InventoryTrendsResponse(BaseModel):
    """GET /dealers/{dealerId}/inventory/trends"""
    success: bool = True
    data: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────
# Response Schemas — Search
# ──────────────────────────────────────────────────

class SearchResultItem(BaseModel):
    battery_id: int
    serial_number: str
    model_name: str = ""
    health: float = 100.0
    status: str = ""
    location: str = ""
    match_score: float = 1.0
    model_config = ConfigDict(protected_namespaces=())


class InventorySearchResponse(BaseModel):
    """GET /dealers/{dealerId}/inventory/search"""
    success: bool = True
    data: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)
