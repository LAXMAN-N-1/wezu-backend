from __future__ import annotations
from pydantic import BaseModel
from typing import List

class ShelfResponse(BaseModel):
    id: int
    name: str
    capacity: int
    battery_ids: List[str]

class RackResponse(BaseModel):
    id: int
    name: str
    shelves: List[ShelfResponse]

class WarehouseStructureResponse(BaseModel):
    id: int
    name: str
    racks: List[RackResponse]

class WarehouseWrapper(BaseModel):
    success: bool
    data: WarehouseStructureResponse

class WarehouseStructureListWrapper(BaseModel):
    success: bool
    data: List[WarehouseStructureResponse]

class BatteryAssignRequest(BaseModel):
    battery_id: str

class ShelfDataResponse(BaseModel):
    success: bool
    data: ShelfResponse
