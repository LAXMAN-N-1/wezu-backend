from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Any
from app.api.deps import get_db
from app.schemas.warehouse import WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.services.warehouse import warehouse_service

router = APIRouter()

@router.get("/", response_model=List[WarehouseRead])
def read_warehouses(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve warehouses.
    """
    warehouses = warehouse_service.get_warehouses(db, skip=skip, limit=limit)
    return warehouses

@router.post("/", response_model=WarehouseRead)
def create_warehouse(
    *,
    db: Session = Depends(get_db),
    warehouse_in: WarehouseCreate,
) -> Any:
    """
    Create new warehouse.
    """
    warehouse = warehouse_service.create_warehouse(db=db, warehouse_in=warehouse_in)
    return warehouse

@router.get("/{id}", response_model=WarehouseRead)
def read_warehouse(
    *,
    db: Session = Depends(get_db),
    id: int,
) -> Any:
    """
    Get warehouse by ID.
    """
    warehouse = warehouse_service.get_warehouse(db=db, warehouse_id=id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse

@router.put("/{id}", response_model=WarehouseRead)
def update_warehouse(
    *,
    db: Session = Depends(get_db),
    id: int,
    warehouse_in: WarehouseUpdate,
) -> Any:
    """
    Update a warehouse.
    """
    warehouse = warehouse_service.update_warehouse(db=db, warehouse_id=id, warehouse_in=warehouse_in)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse

@router.delete("/{id}", response_model=WarehouseRead)
def delete_warehouse(
    *,
    db: Session = Depends(get_db),
    id: int,
) -> Any:
    """
    Delete a warehouse.
    """
    warehouse = warehouse_service.delete_warehouse(db=db, warehouse_id=id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse
