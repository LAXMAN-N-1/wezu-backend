from app.core.config import settings
import httpx
import logging
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)

class MapsService:
    @staticmethod
    async def geocode(address: str):
        if not settings.GOOGLE_MAPS_API_KEY:
            # Mock
            return {"lat": 12.9716, "lng": 77.5946} # Bangalore
            
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": settings.GOOGLE_MAPS_API_KEY}
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, params=params)
            data = r.json()
            if data['status'] == 'OK':
                return data['results'][0]['geometry']['location']
        except Exception:
            logger.exception("Maps geocoding failed")
        return None

    @staticmethod
    async def get_distance(origin, destination):
        """Return distance in kilometers between two lat/lon points."""
        try:
            if (
                isinstance(origin, dict)
                and isinstance(destination, dict)
                and settings.GOOGLE_MAPS_API_KEY
            ):
                url = "https://maps.googleapis.com/maps/api/distancematrix/json"
                params = {
                    "origins": f"{origin.get('lat')},{origin.get('lng')}",
                    "destinations": f"{destination.get('lat')},{destination.get('lng')}",
                    "key": settings.GOOGLE_MAPS_API_KEY,
                    "units": "metric",
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                data = response.json()
                rows = data.get("rows") or []
                if rows and rows[0].get("elements"):
                    element = rows[0]["elements"][0]
                    distance = element.get("distance", {}).get("value")
                    if distance is not None:
                        return float(distance) / 1000.0
        except Exception:
            logger.exception("Maps distance matrix request failed")

        if not isinstance(origin, dict) or not isinstance(destination, dict):
            return None
        return MapsService.haversine(
            float(origin.get("lng", 0.0)),
            float(origin.get("lat", 0.0)),
            float(destination.get("lng", 0.0)),
            float(destination.get("lat", 0.0)),
        )

    @staticmethod
    def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Calculate great-circle distance in kilometers."""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371 * c
