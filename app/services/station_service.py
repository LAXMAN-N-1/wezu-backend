from sqlmodel import Session, select
from app.models.station import Station, StationImage, StationSlot
from app.models.battery import Battery
from app.schemas.station import StationCreate
from typing import List, Optional
from math import radians, cos, sin, asin, sqrt

class StationService:
    @staticmethod
    def get_stations(db: Session, skip: int = 0, limit: int = 100) -> List[Station]:
        from sqlalchemy.orm import selectinload
        return db.exec(
            select(Station)
            .options(selectinload(Station.images))
            .offset(skip).limit(limit)
        ).all()

    @staticmethod
    def get_nearby(db: Session, lat: float, lon: float, radius_km: float = 50.0) -> List[Station]:
        # Simple Haversine approximation or usage of PostGIS if available.
        # For MVP/Python implementation, we fetch stations and filter.
        # Optimization: Filter by bounding box first if large dataset.
        stations = db.exec(select(Station)).all()
        nearby = []
        for station in stations:
            dist = StationService.haversine(lat, lon, station.latitude, station.longitude)
            if dist <= radius_km:
                # Attach distance dynamically if needed by pydantic wrapper, 
                # but usually we return a tuple or special object.
                # Here we just return Station objects, sorting can happen here.
                station.distance = dist # Monkey patch for response
                nearby.append(station)
        
        nearby.sort(key=lambda s: s.distance)
        return nearby

    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        r = 6371 # Radius of earth in kilometers
        return c * r

    @staticmethod
    def create_station(db: Session, station_in: StationCreate) -> Station:
        station = Station(**station_in.dict())
        db.add(station)
        db.commit()
        db.refresh(station)
        return station

    @staticmethod
    def get_available_slots(db: Session, station_id: int) -> List[StationSlot]:
        return db.exec(
            select(StationSlot).where(
                StationSlot.station_id == station_id, 
                StationSlot.status == "empty"
            )
        ).all()

    @staticmethod
    def assign_battery_to_slot(db: Session, slot_id: int, battery_id: int):
        slot = db.get(StationSlot, slot_id)
        if not slot:
            return None
        
        slot.battery_id = battery_id
        slot.status = "charging"
        slot.is_locked = True
        
        # Update Battery location
        battery = db.get(Battery, battery_id)
        if battery:
            battery.location_type = "station"
            battery.location_id = slot.station_id
            db.add(battery)
            
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    @staticmethod
    def release_battery_from_slot(db: Session, slot_id: int):
        slot = db.get(StationSlot, slot_id)
        if not slot:
            return None
        
        slot.battery_id = None
        slot.status = "empty"
        slot.is_locked = False
        
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

