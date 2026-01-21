from sqlmodel import Session, select
from app.models.geofence import Geofence
from app.services.maps_service import MapsService
from typing import List

class GeofenceService:
    @staticmethod
    def check_boundary(db: Session, lat: float, lon: float) -> bool:
        """
        Check if location is inside any active geofence.
        Returns True if inside allowed zones (or if no zones defined), False if outside.
        Logic can be inverted based on business requirement (Allowed Zones vs Restricted Zones).
        Assuming Allowed Zones (Service Areas).
        """
        geofences = db.exec(select(Geofence).where(Geofence.is_active == True)).all()
        if not geofences:
            return True 

        # 1. Check Restricted Zones (Must be outside ALL)
        restricted = [g for g in geofences if g.type == "restricted_zone"]
        for fence in restricted:
            distance_km = MapsService.haversine(lon, lat, fence.longitude, fence.latitude)
            if (distance_km * 1000) <= fence.radius_meters:
                return False # Inside Restricted Zone -> Violation

        # 2. Check Safe Zones (Must be inside AT LEAST ONE)
        safe = [g for g in geofences if g.type == "safe_zone"]
        if not safe:
            return True # No safe zones defined, assume everywhere is safe (except restricted)

        for fence in safe:
            distance_km = MapsService.haversine(lon, lat, fence.longitude, fence.latitude)
            if (distance_km * 1000) <= fence.radius_meters:
                return True # Inside Safe Zone

        return False # Outside all Safe Zones

    @staticmethod
    def create_geofence(db: Session, name: str, lat: float, lon: float, radius: float) -> Geofence:
        geofence = Geofence(name=name, latitude=lat, longitude=lon, radius_meters=radius)
        db.add(geofence)
        db.commit()
        db.refresh(geofence)
        return geofence
