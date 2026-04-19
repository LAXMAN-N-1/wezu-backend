from __future__ import annotations
from typing import List, Optional
from sqlmodel import func, select, Session
from fastapi import HTTPException

from app.models.stock import Stock
from app.models.stock_movement import StockMovement, StockTransactionType, StockMovementDirection
from app.models.battery import Battery
from app.schemas.stock import StockReceiveRequest, StockTransferRequest, StockAdjustmentRequest, StockCreate, StockUpdate
from app.repositories.stock import StockRepository, StockMovementRepository

class StockService:
    def __init__(self, session: Session):
        self.session = session
        self.stock_repo = StockRepository(session)
        self.movement_repo = StockMovementRepository(session)

    def get_stock(self, warehouse_id: int, product_id: int) -> Optional[Stock]:
        return self.stock_repo.get_by_warehouse_and_product(warehouse_id, product_id)

    def receive_stock(self, request: StockReceiveRequest, user_id: int) -> Stock:
        # 1. Get or Create Stock Record
        stock = self.stock_repo.get_by_warehouse_and_product(request.warehouse_id, request.product_id)
        if not stock:
            stock = self.stock_repo.create(
                db=self.session,
                obj_in=StockCreate(
                    warehouse_id=request.warehouse_id,
                    product_id=request.product_id
                )
            )

        # 2. Update Quantities
        stock.quantity_on_hand += request.quantity
        stock.quantity_available += request.quantity
        self.session.add(stock)

        # 3. Create Movement Record
        movement = StockMovement(
            stock_id=stock.id,
            transaction_type=StockTransactionType.GRN,
            quantity=request.quantity,
            direction=StockMovementDirection.IN,
            reference_type="GRN",
            reference_id=request.reference_id,
            notes=request.notes,
            created_by=user_id
        )
        self.session.add(movement)
        
        # 4. Handle Serial Numbers (Batteries)
        if request.serial_numbers:
            for serial in request.serial_numbers:
                # Find existing battery or create (simplified logic: update existing only for now)
                # In real scenario, might need to create battery here if it's new
                battery = self.session.exec(select(Battery).where(Battery.serial_number == serial)).first()
                if battery:
                    battery.warehouse_id = request.warehouse_id
                    self.session.add(battery)
                # Else: logic to create new battery could go here
        
        self.session.commit()
        self.session.refresh(stock)
        return stock

    def transfer_stock(self, request: StockTransferRequest, user_id: int) -> List[Stock]:
        # 1. Validate Source Stock
        source_stock = self.stock_repo.get_by_warehouse_and_product(request.from_warehouse_id, request.product_id)
        if not source_stock or source_stock.quantity_available < request.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock in source warehouse")

        # 2. Debit Source
        source_stock.quantity_on_hand -= request.quantity
        source_stock.quantity_available -= request.quantity
        self.session.add(source_stock)
        
        source_movement = StockMovement(
            stock_id=source_stock.id,
            transaction_type=StockTransactionType.TRANSFER_OUT,
            quantity=request.quantity,
            direction=StockMovementDirection.OUT,
            reference_type="TRANSFER",
            reference_id=f"TO-{request.to_warehouse_id}",
            notes=request.notes,
            created_by=user_id
        )
        self.session.add(source_movement)

        # 3. Credit Destination
        dest_stock = self.stock_repo.get_by_warehouse_and_product(request.to_warehouse_id, request.product_id)
        if not dest_stock:
            dest_stock = self.stock_repo.create(
                db=self.session,
                obj_in=StockCreate(
                    warehouse_id=request.to_warehouse_id,
                    product_id=request.product_id
                )
            )
        
        dest_stock.quantity_on_hand += request.quantity
        dest_stock.quantity_available += request.quantity
        self.session.add(dest_stock)

        dest_movement = StockMovement(
            stock_id=dest_stock.id,
            transaction_type=StockTransactionType.TRANSFER_IN,
            quantity=request.quantity,
            direction=StockMovementDirection.IN,
            reference_type="TRANSFER",
            reference_id=f"FROM-{request.from_warehouse_id}",
            notes=request.notes,
            created_by=user_id
        )
        self.session.add(dest_movement)

        self.session.commit()
        self.session.refresh(source_stock)
        self.session.refresh(dest_stock)
        return [source_stock, dest_stock]

    def adjust_stock(self, request: StockAdjustmentRequest, user_id: int) -> Stock:
        stock = self.stock_repo.get_by_warehouse_and_product(request.warehouse_id, request.product_id)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock record not found")

        movement_direction = StockMovementDirection.IN
        
        if request.type == StockTransactionType.DAMAGED:
            if stock.quantity_available < request.quantity:
                raise HTTPException(status_code=400, detail="Insufficient available stock to mark as damaged")
            stock.quantity_available -= request.quantity
            stock.quantity_damaged += request.quantity
            movement_direction = StockMovementDirection.OUT # Technically stock is still there but moved to damaged category. 
            # Or we can treat movement as 'status change'. 
            # Let's keep it simple: It's an internal movement. 
            # But StockMovement needs IN/OUT.
            # If we just move availability, maybe we don't change 'quantity_on_hand'.
            # 'Damaged' implies it is physically there but not sellable.
            # So quantity_on_hand stays same, available decreases, damaged increases.
            # This logic fits 'Status Change'.
            # However, StockMovement usually tracks quantity_on_hand changes?
            # Or just any change?
            # Let's log it. Direction is conceptual. 
            # Creating a movement record is good.
            movement_direction = StockMovementDirection.OUT # From available pool
            
        elif request.type == StockTransactionType.ADJUSTMENT_ADD:
            stock.quantity_on_hand += request.quantity
            stock.quantity_available += request.quantity
            movement_direction = StockMovementDirection.IN
            
        elif request.type == StockTransactionType.ADJUSTMENT_SUB:
            if stock.quantity_available < request.quantity:
                 raise HTTPException(status_code=400, detail="Insufficient available stock")
            stock.quantity_on_hand -= request.quantity
            stock.quantity_available -= request.quantity
            movement_direction = StockMovementDirection.OUT

        self.session.add(stock)

        movement = StockMovement(
            stock_id=stock.id,
            transaction_type=request.type,
            quantity=request.quantity,
            direction=movement_direction,
            reference_type="ADJUSTMENT",
            notes=request.notes,
            created_by=user_id
        )
        self.session.add(movement)
        
        self.session.commit()
        self.session.refresh(stock)
        return stock
