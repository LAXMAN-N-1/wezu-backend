from pydantic import BaseModel
from typing import List, Union
from app.schemas.station import NearbyStationResponse

class LatLng(BaseModel):
    lat: float
    lng: float

class ClusterBounds(BaseModel):
    sw: LatLng
    ne: LatLng

class ClusterResponse(BaseModel):
    id: str
    center: LatLng
    station_count: int
    bounds: ClusterBounds
    stations: List[NearbyStationResponse] = []

class ClusteringResult(BaseModel):
    clusters: List[Union[ClusterResponse, NearbyStationResponse]]
    total_stations: int
    zoom_level: int
