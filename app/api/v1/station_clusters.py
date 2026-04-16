from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas.cluster import ClusteringResult
from app.schemas.station import NearbyStationResponse
from app.services.clustering_service import ClusteringService

router = APIRouter()

@router.get("/clusters", response_model=ClusteringResult)
def get_station_clusters_grid(
    lat: float = Query(..., description="Center latitude of the map viewport"),
    lng: float = Query(..., description="Center longitude of the map viewport"),
    zoom_level: int = Query(..., ge=5, le=15, description="Map zoom level (5-15)"),
    bounds: str = Query(..., description="Bounding box sw_lat,sw_lng,ne_lat,ne_lng"),
    db: Session = Depends(deps.get_db)
):
    try:
        return ClusteringService.get_clusters(db, zoom_level, lat, lng, bounds)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/clusters/{cluster_id}/expand", response_model=List[NearbyStationResponse])
def expand_station_cluster_grid(
    cluster_id: str,
    lat: float = Query(0.0, description="Center latitude of user location for distance"),
    lng: float = Query(0.0, description="Center longitude of user location for distance"),
    bounds: str = Query("-90,-180,90,180", description="Bounding box sw_lat,sw_lng,ne_lat,ne_lng"),
    db: Session = Depends(deps.get_db)
):
    try:
        parts = cluster_id.split('_')
        if len(parts) != 4:
            raise ValueError("Invalid format")
        zoom_level = int(parts[1])
        return ClusteringService.expand_cluster(db, cluster_id, zoom_level, lat, lng, bounds)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))