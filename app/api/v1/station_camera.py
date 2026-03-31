from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.services.station_camera_service import StationCameraService
from app.schemas.station_camera import StationCameraResponse, StationCameraCreate, StationCameraUpdate

router = APIRouter()

@router.get("/{station_id}", response_model=List[StationCameraResponse])
def get_station_cameras(station_id: int, db: Session = Depends(deps.get_db)):
    service = StationCameraService(db)
    return service.get_cameras_by_station(station_id)

@router.post("/{station_id}", response_model=StationCameraResponse)
def add_station_camera(station_id: int, camera_data: StationCameraCreate, db: Session = Depends(deps.get_db)):
    service = StationCameraService(db)
    return service.create_camera(station_id, camera_data)

@router.put("/{station_id}/{camera_id}", response_model=StationCameraResponse)
def update_station_camera(station_id: int, camera_id: int, update_data: StationCameraUpdate, db: Session = Depends(deps.get_db)):
    service = StationCameraService(db)
    return service.update_camera(station_id, camera_id, update_data)

@router.delete("/{station_id}/{camera_id}")
def delete_station_camera(station_id: int, camera_id: int, db: Session = Depends(deps.get_db)):
    service = StationCameraService(db)
    return service.delete_camera(station_id, camera_id)
