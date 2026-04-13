from pydantic import BaseModel
from typing import List

class StationData(BaseModel):
    name: str
    distance_km: float

class ExpiryNotificationPayload(BaseModel):
    milestone_hours: int
    nearest_stations: List[StationData]
    deep_link: str
