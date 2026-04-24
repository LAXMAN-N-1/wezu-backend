from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.geofence import Geofence
from app.services.maps_service import MapsService


class GeofenceService:
    SAFE_ZONE_TYPES = {"safe_zone", "station_perimeter"}
    RESTRICTED_ZONE_TYPES = {"restricted_zone"}

    @staticmethod
    def is_inside_geofence(lat: float, lon: float, geofence: Geofence) -> bool:
        distance_km = MapsService.haversine(lon, lat, geofence.longitude, geofence.latitude)
        return (distance_km * 1000.0) <= float(geofence.radius_meters or 0)

    @staticmethod
    def check_boundary(lat: float, lon: float, geofence: Geofence) -> bool:
        """
        Backward-compatible boundary check.
        Returns True when this specific geofence is violated.
        """
        zone_type = str(geofence.type or "").strip().lower()
        inside = GeofenceService.is_inside_geofence(lat, lon, geofence)
        if zone_type in GeofenceService.RESTRICTED_ZONE_TYPES:
            return inside
        if zone_type in GeofenceService.SAFE_ZONE_TYPES:
            return not inside
        return False

    @staticmethod
    def evaluate_location(
        db: Session,
        lat: float,
        lon: float,
        *,
        geofences: list[Geofence] | None = None,
    ) -> dict[str, Any]:
        geofence_rows = (
            geofences
            if geofences is not None
            else db.exec(select(Geofence).where(Geofence.is_active == True)).all()  # noqa: E712
        )
        if not geofence_rows:
            return {
                "is_allowed": True,
                "is_violation": False,
                "violations": [],
                "outside_safe_zone": False,
            }

        restricted_hits: list[Geofence] = []
        safe_zones: list[Geofence] = []
        safe_inside_count = 0

        for fence in geofence_rows:
            zone_type = str(fence.type or "").strip().lower()
            inside = GeofenceService.is_inside_geofence(lat, lon, fence)
            if zone_type in GeofenceService.RESTRICTED_ZONE_TYPES:
                if inside:
                    restricted_hits.append(fence)
            elif zone_type in GeofenceService.SAFE_ZONE_TYPES:
                safe_zones.append(fence)
                if inside:
                    safe_inside_count += 1

        violations: list[dict[str, Any]] = [
            {
                "geofence_id": hit.id,
                "name": hit.name,
                "type": hit.type,
                "reason": "inside_restricted_zone",
            }
            for hit in restricted_hits
        ]

        outside_safe_zone = bool(safe_zones and safe_inside_count == 0)
        if outside_safe_zone:
            violations.append(
                {
                    "geofence_id": None,
                    "name": "Safe Zone Boundary",
                    "type": "safe_zone",
                    "reason": "outside_all_safe_zones",
                }
            )

        is_violation = bool(violations)
        return {
            "is_allowed": not is_violation,
            "is_violation": is_violation,
            "violations": violations,
            "outside_safe_zone": outside_safe_zone,
            "restricted_hits": len(restricted_hits),
            "safe_zones_total": len(safe_zones),
            "safe_zones_inside": safe_inside_count,
        }

    @staticmethod
    def is_location_allowed(db: Session, lat: float, lon: float) -> bool:
        return bool(GeofenceService.evaluate_location(db, lat, lon).get("is_allowed", True))

    @staticmethod
    def create_geofence(db: Session, name: str, lat: float, lon: float, radius: float) -> Geofence:
        geofence = Geofence(name=name, latitude=lat, longitude=lon, radius_meters=radius)
        db.add(geofence)
        db.commit()
        db.refresh(geofence)
        return geofence
