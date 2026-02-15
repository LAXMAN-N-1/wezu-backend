from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Any
from app.api import deps
from app.api.deps import get_db
from app.models.user import User
from app.models.stock import Stock
from app.schemas.stock import StockResponse, StockReceiveRequest, StockTransferRequest, StockAdjustmentRequest
from app.services.stock import StockService

router = APIRouter()

@router.get("/warehouse/{warehouse_id}", response_model=List[StockResponse])
def read_warehouse_stock(
    *,
    db: Session = Depends(get_db),
    warehouse_id: int,
    current_user: User = Depends(deps.check_permission("stock", "view")),
) -> Any:
    """
    Get all stock in a warehouse.
    """
    # Note: Service generic method might need enhancement for list by warehouse
    # For now, we can use repository directly or add method to service
    # I'll use repository directly via service instance if possible, or add to service
    # Let's add simple filter in repo or service. 
    # For now, let's assume service has get_stock which is single.
    # I'll use list filtered by warehouse_id.
    # Re-instantiating service here.
    service = StockService(db)
    # The repository has filter method.
    return service.stock_repo.get_multi_by_field(db, "warehouse_id", warehouse_id)

@router.get("/product/{product_id}", response_model=List[StockResponse])
def read_product_stock(
    *,
    db: Session = Depends(get_db),
    product_id: int,
    current_user: User = Depends(deps.check_permission("stock", "view")),
) -> Any:
    """
    Get stock of a product across all warehouses.
    """
    service = StockService(db)
    return service.stock_repo.get_multi_by_field(db, "product_id", product_id)

@router.post("/receive", response_model=StockResponse)
def receive_stock(
    *,
    db: Session = Depends(get_db),
    request: StockReceiveRequest,
    current_user: User = Depends(deps.check_permission("stock", "create")),
) -> Any:
    """
    Receive stock (GRN).
    """
    service = StockService(db)
    return service.receive_stock(request, user_id=current_user.id)

@router.post("/transfer", response_model=List[StockResponse])
def transfer_stock(
    *,
    db: Session = Depends(get_db),
    request: StockTransferRequest,
    current_user: User = Depends(deps.check_permission("stock", "edit")),
) -> Any:
    """
    Transfer stock between warehouses.
    """
    service = StockService(db)
    return service.transfer_stock(request, user_id=current_user.id)

@router.post("/adjust", response_model=StockResponse)
def adjust_stock(
    *,
    db: Session = Depends(get_db),
    request: StockAdjustmentRequest,
    current_user: User = Depends(deps.check_permission("stock", "edit")),
) -> Any:
    """
    Adjust stock manually.
    """
    service = StockService(db)
    return service.adjust_stock(request, user_id=current_user.id)
