from __future__ import annotations
"""
Station Repository
Data access layer for Station model
"""
from typing import Optional, List
from sqlmodel import Session, select, func
from app.models.station import Station
from app.repositories.base_repository import BaseRepository
from pydantic import BaseModel


class StationCreate(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    total_slots: int
    max_capacity: int = 0


class StationUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    total_slots: Optional[int] = None
    max_capacity: Optional[int] = None


class StationRepository(BaseRepository[Station, StationCreate, StationUpdate]):
    """Station-specific data access methods"""
    
    def __init__(self):
        super().__init__(Station)
    
    def get_active_stations(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Station]:
        """Get all active stations"""
        query = select(Station).where(
            Station.status == "active"
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def get_nearby_stations(
        self,
        db: Session,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        *,
        limit: int = 10
    ) -> List[Station]:
        """Get nearby stations within radius (simplified - use PostGIS in production)"""
        # Simplified distance calculation (Haversine formula should be used)
        lat_diff = radius_km / 111.0  # 1 degree latitude ≈ 111 km
        lon_diff = radius_km / (111.0 * func.cos(func.radians(latitude)))
        
        query = select(Station).where(
            (Station.status == "active") &
            (Station.latitude.between(latitude - lat_diff, latitude + lat_diff)) &
            (Station.longitude.between(longitude - lon_diff, longitude + lon_diff))
        ).limit(limit)
        
        return list(db.exec(query).all())
    
    def search_stations(
        self,
        db: Session,
        search_term: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Station]:
        """Search stations by name or address"""
        query = select(Station).where(
            (Station.name.contains(search_term)) |
            (Station.address.contains(search_term))
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())


# Singleton instance
station_repository = StationRepository()
