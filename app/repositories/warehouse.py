from app.repositories.base_repository import BaseRepository
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from sqlmodel import Session

class WarehouseRepository(BaseRepository[Warehouse, WarehouseCreate, WarehouseUpdate]):
    def __init__(self):
        super().__init__(model=Warehouse)

warehouse_repository = WarehouseRepository()
