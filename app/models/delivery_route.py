from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.models.user import User
from app.models.delivery_assignment import DeliveryAssignment
from app.models.driver_profile import DriverProfile

class DeliveryRoute(SQLModel, table=True):
    __tablename__ = "delivery_routes"
    """Optimized delivery routes for drivers"""
    id: Optional[int] = Field(default=None, primary_key=True)
    driver_id: int = Field(foreign_key="driver_profiles.id")
    
    route_name: str  # e.g., "North Delhi Route - 2024-12-22"
    status: str = Field(default="PLANNED")  # PLANNED, IN_PROGRESS, COMPLETED, CANCELLED
    
    total_stops: int = Field(default=0)
    completed_stops: int = Field(default=0)
    
    estimated_distance_km: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    actual_distance_km: Optional[float] = None
    actual_duration_minutes: Optional[int] = None
    
    # Optimized waypoints as GeoJSON or array of coordinates
    optimized_path: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    driver: "DriverProfile" = Relationship()
    stops: list["RouteStop"] = Relationship(back_populates="route")

class RouteStop(SQLModel, table=True):
    __tablename__ = "route_stops"
    """Individual stops in a delivery route"""
    id: Optional[int] = Field(default=None, primary_key=True)
    route_id: int = Field(foreign_key="delivery_routes.id")
    delivery_assignment_id: int = Field(foreign_key="delivery_assignments.id")
    
    stop_sequence: int  # Order in the route (1, 2, 3...)
    stop_type: str = Field(default="DELIVERY")  # PICKUP, DELIVERY, RETURN
    
    address: str
    latitude: float
    longitude: float
    
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    status: str = Field(default="PENDING")  # PENDING, ARRIVED, COMPLETED, FAILED, SKIPPED
    failure_reason: Optional[str] = None
    
    notes: Optional[str] = None
    
    # Relationships
    route: DeliveryRoute = Relationship(back_populates="stops")
    delivery: "DeliveryAssignment" = Relationship()
