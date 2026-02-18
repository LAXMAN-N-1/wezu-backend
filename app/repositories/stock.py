from typing import List, Optional
from sqlmodel import Session, select, func
from app.repositories.base_repository import BaseRepository
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.schemas.stock import StockCreate, StockUpdate, StockMovementBase

class StockRepository(BaseRepository[Stock, StockCreate, StockUpdate]):
    def __init__(self, session: Session):
        super().__init__(model=Stock)
        self.session = session

    def get_by_warehouse_and_product(self, warehouse_id: int, product_id: int) -> Optional[Stock]:
        query = select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.product_id == product_id
        )
        return self.session.exec(query).first()

    def get_total_product_stock(self, product_id: int) -> int:
        query = select(func.sum(Stock.quantity_available)).where(Stock.product_id == product_id)
        result = self.session.exec(query).first()
        return result if result else 0

class StockMovementRepository(BaseRepository[StockMovement, StockMovementBase, StockMovementBase]):
    # StockMovement is immutable, so UpdateSchema is same as Create or Base (not used for updates)
    def __init__(self, session: Session):
        super().__init__(model=StockMovement)
        self.session = session

    def get_by_stock_id(self, stock_id: int, skip: int = 0, limit: int = 100) -> List[StockMovement]:
        query = select(StockMovement).where(StockMovement.stock_id == stock_id).order_by(StockMovement.created_at.desc()).offset(skip).limit(limit)
        return list(self.session.exec(query).all())
