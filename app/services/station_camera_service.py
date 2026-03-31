from sqlmodel import Session, select
from fastapi import HTTPException
from app.models.station_camera import StationCamera
from app.schemas.station_camera import StationCameraCreate, StationCameraUpdate
from datetime import datetime

class StationCameraService:
    def __init__(self, session: Session):
        self.session = session
        
    def get_cameras_by_station(self, station_id: int):
        statement = select(StationCamera).where(StationCamera.station_id == station_id)
        return self.session.exec(statement).all()
        
    def create_camera(self, station_id: int, camera_data: StationCameraCreate):
        camera = StationCamera(
            station_id=station_id,
            name=camera_data.name,
            rtsp_url=camera_data.rtsp_url,
            status=camera_data.status
        )
        self.session.add(camera)
        self.session.commit()
        self.session.refresh(camera)
        return camera
        
    def update_camera(self, station_id: int, camera_id: int, update_data: StationCameraUpdate):
        camera = self.session.get(StationCamera, camera_id)
        if not camera or camera.station_id != station_id:
            raise HTTPException(status_code=404, detail="Camera not found")
            
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(camera, key, value)
            
        camera.updated_at = datetime.utcnow()
        self.session.add(camera)
        self.session.commit()
        self.session.refresh(camera)
        return camera
        
    def delete_camera(self, station_id: int, camera_id: int):
        camera = self.session.get(StationCamera, camera_id)
        if not camera or camera.station_id != station_id:
            raise HTTPException(status_code=404, detail="Camera not found")
            
        self.session.delete(camera)
        self.session.commit()
        return {"ok": True}
