import math
from typing import List, Union
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.models.station import Station, StationSlot, StationImage
from app.schemas.cluster import ClusterResponse, ClusteringResult, ClusterBounds, LatLng
from app.schemas.station import NearbyStationResponse, StationImageResponse
from app.services.station_service import StationService

class ClusteringService:
    @staticmethod
    def _parse_bounds(bounds_str: str):
        parts = bounds_str.split(',')
        if len(parts) != 4:
            raise ValueError("Invalid bounds format. Expected sw_lat,sw_lng,ne_lat,ne_lng")
        return [float(p) for p in parts]

    @staticmethod
    def _build_station_response(station: Station, lat: float, lng: float, availability_map: dict) -> NearbyStationResponse:
        dist = StationService.haversine(lng, lat, station.longitude, station.latitude)
        return NearbyStationResponse(
            id=station.id,
            name=station.name,
            latitude=station.latitude,
            longitude=station.longitude,
            distance_km=round(dist, 2),
            address=station.address,
            zone_id=station.zone_id,
            station_type=station.station_type,
            status=station.status,
            is_24x7=station.is_24x7,
            available_batteries=availability_map.get(station.id, 0),
            available_slots=station.available_slots,
            rating=station.rating,
            images=[
                StationImageResponse(url=img.url, is_primary=img.is_primary)
                for img in station.images
            ]
        )

    @staticmethod
    def get_clusters(db: Session, zoom_level: int, lat: float, lng: float, bounds_str: str) -> ClusteringResult:
        sw_lat, sw_lng, ne_lat, ne_lng = ClusteringService._parse_bounds(bounds_str)
        grid_size = 360.0 / (2.0 ** zoom_level)
        
        query = select(Station).where(
            and_(
                Station.latitude >= sw_lat,
                Station.latitude <= ne_lat,
                Station.longitude >= sw_lng,
                Station.longitude <= ne_lng
            )
        )
        stations = db.execute(query).scalars().all()
        
        availability_query = (
            select(StationSlot.station_id, func.count(StationSlot.id))
            .where(StationSlot.status == "ready")
            .group_by(StationSlot.station_id)
        )
        availability_map = dict(db.execute(availability_query).all())
        
        grid = {}
        for station in stations:
            cell_x = math.floor(station.longitude / grid_size)
            cell_y = math.floor(station.latitude / grid_size)
            cell_key = (cell_x, cell_y)
            if cell_key not in grid:
                grid[cell_key] = []
            grid[cell_key].append(station)
            
        clusters = []
        for (cell_x, cell_y), cell_stations in grid.items():
            if len(cell_stations) == 1:
                clusters.append(ClusteringService._build_station_response(cell_stations[0], lat, lng, availability_map))
            else:
                avg_lat = sum(s.latitude for s in cell_stations) / len(cell_stations)
                avg_lng = sum(s.longitude for s in cell_stations) / len(cell_stations)
                
                min_lat = min(s.latitude for s in cell_stations)
                max_lat = max(s.latitude for s in cell_stations)
                min_lng = min(s.longitude for s in cell_stations)
                max_lng = max(s.longitude for s in cell_stations)
                
                cluster_id = f"cluster_{zoom_level}_{cell_x}_{cell_y}"
                cluster = ClusterResponse(
                    id=cluster_id,
                    center=LatLng(lat=avg_lat, lng=avg_lng),
                    station_count=len(cell_stations),
                    bounds=ClusterBounds(
                        sw=LatLng(lat=min_lat, lng=min_lng),
                        ne=LatLng(lat=max_lat, lng=max_lng)
                    ),
                    stations=[]
                )
                clusters.append(cluster)
                
        return ClusteringResult(
            clusters=clusters,
            total_stations=len(stations),
            zoom_level=zoom_level
        )

    @staticmethod
    def expand_cluster(db: Session, cluster_id: str, zoom_level: int, lat: float, lng: float, bounds_str: str) -> List[NearbyStationResponse]:
        sw_lat, sw_lng, ne_lat, ne_lng = ClusteringService._parse_bounds(bounds_str)
        grid_size = 360.0 / (2.0 ** zoom_level)
        
        parts = cluster_id.split('_')
        if len(parts) != 4 or parts[0] != "cluster":
            raise ValueError("Invalid cluster ID format")
            
        cell_x = int(parts[2])
        cell_y = int(parts[3])
        
        query = select(Station).where(
            and_(
                Station.latitude >= (cell_y * grid_size),
                Station.latitude < ((cell_y + 1) * grid_size),
                Station.longitude >= (cell_x * grid_size),
                Station.longitude < ((cell_x + 1) * grid_size),
                Station.latitude >= sw_lat,
                Station.latitude <= ne_lat,
                Station.longitude >= sw_lng,
                Station.longitude <= ne_lng
            )
        )
        stations = db.execute(query).scalars().all()
        
        availability_query = (
            select(StationSlot.station_id, func.count(StationSlot.id))
            .where(StationSlot.status == "ready")
            .group_by(StationSlot.station_id)
        )
        availability_map = dict(db.execute(availability_query).all())
        
        result = []
        for station in stations:
            result.append(ClusteringService._build_station_response(station, lat, lng, availability_map))
            
        return result
