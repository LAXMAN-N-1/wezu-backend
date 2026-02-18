from sqlmodel import Session
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.repositories.warehouse import warehouse_repository
from typing import List, Optional

class WarehouseService:
    @staticmethod
    def get_warehouses(db: Session, skip: int = 0, limit: int = 100) -> List[Warehouse]:
        return warehouse_repository.get_multi(db, skip=skip, limit=limit)

    @staticmethod
    def get_warehouse(db: Session, warehouse_id: int) -> Optional[Warehouse]:
        return warehouse_repository.get(db, id=warehouse_id)

    @staticmethod
    def create_warehouse(db: Session, warehouse_in: WarehouseCreate) -> Warehouse:
        return warehouse_repository.create(db, obj_in=warehouse_in)

    @staticmethod
    def update_warehouse(db: Session, warehouse_id: int, warehouse_in: WarehouseUpdate) -> Optional[Warehouse]:
        db_obj = warehouse_repository.get(db, id=warehouse_id)
        if not db_obj:
            return None
        return warehouse_repository.update(db, db_obj=db_obj, obj_in=warehouse_in)

    @staticmethod
    def delete_warehouse(db: Session, warehouse_id: int) -> Optional[Warehouse]:
        if not warehouse_repository.get(db, id=warehouse_id):
            return None
        return warehouse_repository.delete(db, id=warehouse_id)

warehouse_service = WarehouseService()
