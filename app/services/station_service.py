from sqlmodel import Session, select, func
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
    def get_nearby(
        db: Session, 
        lat: float, 
        lon: float, 
        radius_km: float = 50.0,
        min_rating: Optional[float] = None,
        status: Optional[str] = None,
        is_24x7: Optional[bool] = None,
        sort_by: str = "distance"
    ) -> List['NearbyStationResponse']:
        from app.schemas.station import NearbyStationResponse, StationImageResponse
        
        # 1. Base Query
        query = select(Station)
        if status:
            query = query.where(Station.status == status)
        if min_rating:
            query = query.where(Station.rating >= min_rating)
        if is_24x7:
             query = query.where(Station.is_24x7 == True)
             
        stations = db.execute(query).scalars().all()
        
        # 2. Get Availability Map (Optimized)
        availability_query = select(StationSlot.station_id, func.count(StationSlot.id)).where(StationSlot.status == "ready").group_by(StationSlot.station_id)
        availability_results = db.execute(availability_query).all()
        availability_map = {r[0]: r[1] for r in availability_results}
        
        nearby = []
        for station in stations:
            dist = StationService.haversine(lon, lat, station.longitude, station.latitude)
            if dist <= radius_km:
                # Create the response object
                station_data = station.model_dump()
                # Images need to be converted to schemas too if the relation is loaded
                # For simplicity, we can load images or just pass empty for now if not needed
                # However, StationResponse expects List[StationImageResponse]
                images = [StationImageResponse(url=img.url, is_primary=img.is_primary) for img in station.images]
                
                nearby_station = NearbyStationResponse(
                    **station_data,
                    images=images,
                    distance=dist,
                    available_batteries=availability_map.get(station.id, 0)
                )
                nearby.append(nearby_station)
        
        # 3. Sort
        if sort_by == "rating":
            nearby.sort(key=lambda s: s.rating, reverse=True)
        elif sort_by == "availability":
            nearby.sort(key=lambda s: s.available_batteries, reverse=True)
        else: # distance (default)
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
        return db.execute(
            select(StationSlot).where(
                StationSlot.station_id == station_id, 
                StationSlot.status == "empty"
            )
        ).scalars().all()

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

