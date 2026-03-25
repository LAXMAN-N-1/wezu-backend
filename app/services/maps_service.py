from app.core.config import settings
import httpx

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
        except Exception as e:
            print(f"Maps Error: {e}")
        return None

    @staticmethod
    def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Calculate the great circle distance between two points in km."""
        from math import radians, cos, sin, asin, sqrt
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        r = 6371 # Radius of earth in km
        return c * r
