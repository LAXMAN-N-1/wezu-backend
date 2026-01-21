"""
Google Maps API Integration
Handles geocoding, distance calculation, and route optimization
"""
import googlemaps
from typing import Dict, Any, List, Tuple, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class GoogleMapsIntegration:
    """Google Maps API wrapper"""
    
    def __init__(self):
        self.client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
    
    def geocode_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Convert address to coordinates
        
        Args:
            address: Address string
            
        Returns:
            Location details with lat/lng
        """
        try:
            result = self.client.geocode(address)
            if result:
                location = result[0]
                return {
                    "formatted_address": location["formatted_address"],
                    "latitude": location["geometry"]["location"]["lat"],
                    "longitude": location["geometry"]["location"]["lng"],
                    "place_id": location.get("place_id")
                }
            return None
        except Exception as e:
            logger.error(f"Geocoding failed for {address}: {str(e)}")
            return None
    
    def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[str]:
        """
        Convert coordinates to address
        
        Args:
            latitude: Latitude
            longitude: Longitude
            
        Returns:
            Formatted address string
        """
        try:
            result = self.client.reverse_geocode((latitude, longitude))
            if result:
                return result[0]["formatted_address"]
            return None
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {str(e)}")
            return None
    
    def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate distance and duration between two points
        
        Args:
            origin: (lat, lng) tuple
            destination: (lat, lng) tuple
            mode: Travel mode (driving, walking, bicycling, transit)
            
        Returns:
            Distance and duration details
        """
        try:
            result = self.client.distance_matrix(
                origins=[origin],
                destinations=[destination],
                mode=mode
            )
            
            if result["rows"]:
                element = result["rows"][0]["elements"][0]
                if element["status"] == "OK":
                    return {
                        "distance_meters": element["distance"]["value"],
                        "distance_text": element["distance"]["text"],
                        "duration_seconds": element["duration"]["value"],
                        "duration_text": element["duration"]["text"]
                    }
            return None
        except Exception as e:
            logger.error(f"Distance calculation failed: {str(e)}")
            return None
    
    def get_directions(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
        waypoints: Optional[List[Tuple[float, float]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get directions between points
        
        Args:
            origin: Starting point (lat, lng)
            destination: Ending point (lat, lng)
            mode: Travel mode
            waypoints: Optional intermediate points
            
        Returns:
            Route details with steps
        """
        try:
            result = self.client.directions(
                origin=origin,
                destination=destination,
                mode=mode,
                waypoints=waypoints
            )
            
            if result:
                route = result[0]
                leg = route["legs"][0]
                
                return {
                    "distance_meters": leg["distance"]["value"],
                    "duration_seconds": leg["duration"]["value"],
                    "start_address": leg["start_address"],
                    "end_address": leg["end_address"],
                    "polyline": route["overview_polyline"]["points"],
                    "steps": [
                        {
                            "instruction": step["html_instructions"],
                            "distance": step["distance"]["text"],
                            "duration": step["duration"]["text"]
                        }
                        for step in leg["steps"]
                    ]
                }
            return None
        except Exception as e:
            logger.error(f"Directions request failed: {str(e)}")
            return None
    
    def find_nearby_places(
        self,
        location: Tuple[float, float],
        radius: int = 5000,
        place_type: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find nearby places
        
        Args:
            location: Center point (lat, lng)
            radius: Search radius in meters
            place_type: Type of place to search for
            keyword: Search keyword
            
        Returns:
            List of nearby places
        """
        try:
            result = self.client.places_nearby(
                location=location,
                radius=radius,
                type=place_type,
                keyword=keyword
            )
            
            places = []
            for place in result.get("results", []):
                places.append({
                    "name": place["name"],
                    "address": place.get("vicinity"),
                    "latitude": place["geometry"]["location"]["lat"],
                    "longitude": place["geometry"]["location"]["lng"],
                    "place_id": place["place_id"],
                    "rating": place.get("rating"),
                    "types": place.get("types", [])
                })
            
            return places
        except Exception as e:
            logger.error(f"Nearby places search failed: {str(e)}")
            return []


# Singleton instance
google_maps_integration = GoogleMapsIntegration()
