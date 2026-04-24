from __future__ import annotations
"""
Logistics delivery schemas: DeliveryAssignment, DeliveryRoute
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime


# ── Delivery Assignment ──────────────────────────────────

class DeliveryAssignmentCreate(BaseModel):
    delivery_order_id: int
    driver_id: int
    vehicle_id: Optional[int] = None
    notes: Optional[str] = None

class DeliveryAssignmentResponse(BaseModel):
    id: int
    delivery_order_id: int
    driver_id: int
    vehicle_id: Optional[int] = None
    status: str = "assigned"
    assigned_at: datetime
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Delivery Route ───────────────────────────────────────

class RouteStopCreate(BaseModel):
    delivery_order_id: int
    sequence: int
    address: str
    latitude: float
    longitude: float
    notes: Optional[str] = None

class RouteStopResponse(BaseModel):
    id: int
    route_id: int
    delivery_order_id: int
    sequence: int
    address: str
    latitude: float
    longitude: float
    status: str = "pending"
    arrived_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DeliveryRouteCreate(BaseModel):
    driver_id: int
    date: datetime
    stops: List[RouteStopCreate] = []

class DeliveryRouteResponse(BaseModel):
    id: int
    driver_id: int
    date: datetime
    status: str = "planned"
    total_distance_km: float = 0.0
    estimated_duration_min: int = 0
    stops: List[RouteStopResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
