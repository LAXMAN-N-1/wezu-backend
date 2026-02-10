from sqlmodel import Session
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.repositories.warehouse import WarehouseRepository
from typing import List, Optional

class WarehouseService:
    @staticmethod
    def get_warehouses(db: Session, skip: int = 0, limit: int = 100) -> List[Warehouse]:
        return WarehouseRepository(db).get_multi(skip=skip, limit=limit)

    @staticmethod
    def get_warehouse(db: Session, warehouse_id: int) -> Optional[Warehouse]:
        return WarehouseRepository(db).get(id=warehouse_id)

    @staticmethod
    def create_warehouse(db: Session, warehouse_in: WarehouseCreate) -> Warehouse:
        return WarehouseRepository(db).create(obj_in=warehouse_in)

    @staticmethod
    def update_warehouse(db: Session, warehouse_id: int, warehouse_in: WarehouseUpdate) -> Optional[Warehouse]:
        repo = WarehouseRepository(db)
        db_obj = repo.get(id=warehouse_id)
        if not db_obj:
            return None
        return repo.update(db_obj=db_obj, obj_in=warehouse_in)

    @staticmethod
    def delete_warehouse(db: Session, warehouse_id: int) -> Optional[Warehouse]:
        repo = WarehouseRepository(db)
        if not repo.get(id=warehouse_id):
            return None
        return repo.remove(id=warehouse_id)

warehouse_service = WarehouseService()
