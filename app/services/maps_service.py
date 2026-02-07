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
    async def get_distance(origin, destination):
        # Calculate distance matrix (Future impl)
        pass
