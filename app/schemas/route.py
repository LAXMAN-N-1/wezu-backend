from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime

class LocationBase(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

class RouteOptimizeRequest(BaseModel):
    driver_id: int = Field(gt=0)
    start_location: LocationBase
    order_ids: List[str] = Field(min_length=1)

class OptimizedWaypoint(BaseModel):
    sequence_index: int
    order_id: str
    location: LocationBase
    estimated_arrival: datetime

class RouteOptimizeResponse(BaseModel):
    route_id: UUID
    optimized_waypoints: List[OptimizedWaypoint]
    overview_polyline: str
    total_distance_meters: int
    total_duration_seconds: int
    traffic_congestion_level: str = "moderate"
