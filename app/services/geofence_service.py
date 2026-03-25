from sqlmodel import Session, select, col
from app.models.geofence import Geofence
from app.services.maps_service import MapsService
from typing import List

class GeofenceService:
    @staticmethod
    def check_boundary(db: Session, lat: float, lon: float) -> tuple[bool, str]:
        """
        Check if location is inside any active geofence.
        Returns (True, "OK") if valid, (False, "Violation Message") if invalid.
        """
        geofences = list(db.exec(select(Geofence).where(col(Geofence.is_active) == True)).all())
        if not geofences:
            return True, "OK"

        # 1. Check Restricted Zones (Must be outside ALL)
        restricted = [g for g in geofences if g.type == "restricted_zone"]
        for fence in restricted:
            distance_km = MapsService.haversine(lon, lat, fence.longitude, fence.latitude)
            if (distance_km * 1000) <= fence.radius_meters:
                return False, f"Entered Restricted Zone: {fence.name}"

        # 2. Check Safe Zones (Must be inside AT LEAST ONE if any safe zones exist)
        safe = [g for g in geofences if g.type == "safe_zone"]
        if not safe:
            return True, "OK"

        for fence in safe:
            distance_km = MapsService.haversine(lon, lat, fence.longitude, fence.latitude)
            if (distance_km * 1000) <= fence.radius_meters:
                return True, "OK"

        return False, "Exited Safe Operational Zones"

    @staticmethod
    def create_geofence(db: Session, name: str, lat: float, lon: float, radius: float) -> Geofence:
        geofence = Geofence(name=name, latitude=lat, longitude=lon, radius_meters=radius)
        db.add(geofence)
        db.commit()
        db.refresh(geofence)
        return geofence
