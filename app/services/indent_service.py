from sqlmodel import Session
from fastapi import HTTPException
from app.models.indent import Indent, IndentItem, IndentStatus
from app.models.stock import Stock
from app.models.stock_movement import StockMovement, StockTransactionType, StockMovementDirection
from app.repositories.indent_repository import IndentRepository
from app.schemas.indent import IndentCreate, IndentApproveRequest

class IndentService:
    def __init__(self, session: Session):
        self.session = session
        self.indent_repo = IndentRepository(session)
        
    def create_indent(self, dealer_id: int, indent_data: IndentCreate) -> Indent:
        indent = Indent(
            dealer_id=dealer_id,
            warehouse_id=indent_data.warehouse_id,
            notes=indent_data.notes,
            status=IndentStatus.PENDING
        )
        
        for item_data in indent_data.items:
            item = IndentItem(
                product_id=item_data.product_id,
                requested_quantity=item_data.requested_quantity
            )
            indent.items.append(item)
            
        return self.indent_repo.create_indent(indent)
        
    def approve_indent(self, indent_id: int, approve_data: IndentApproveRequest) -> Indent:
        indent = self.indent_repo.get_by_id(indent_id)
        if not indent:
            raise HTTPException(status_code=404, detail="Indent not found")
            
        if indent.status != IndentStatus.PENDING:
            raise HTTPException(status_code=400, detail="Indent is not in PENDING state")
            
        indent.manager_notes = approve_data.manager_notes
        
        # Maps item id -> approved quantity
        approvals = {item.item_id: item.approved_quantity for item in approve_data.items}
        
        all_zero = True
        for item in indent.items:
            approved_qty = approvals.get(item.id, 0)
            item.approved_quantity = approved_qty
            if approved_qty > 0:
                all_zero = False
                
        if all_zero:
            indent.status = IndentStatus.REJECTED
        else:
            indent.status = IndentStatus.APPROVED
            
        return self.indent_repo.update(indent)
        
    def dispatch_indent(self, indent_id: int, user_id: int) -> Indent:
        indent = self.indent_repo.get_by_id(indent_id)
        if not indent:
            raise HTTPException(status_code=404, detail="Indent not found")
            
        if indent.status != IndentStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Indent is not APPROVED")
            
        for item in indent.items:
            if item.approved_quantity > 0:
                # Deduct from warehouse stock
                statement = self.session.query(Stock).filter(
                    Stock.warehouse_id == indent.warehouse_id,
                    Stock.product_id == item.product_id
                ).first()
                
                if not statement or statement.quantity_available < item.approved_quantity:
                    raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}")
                    
                # Deduct stock
                statement.quantity_available -= item.approved_quantity
                statement.quantity_on_hand -= item.approved_quantity
                self.session.add(statement)
                
                # Record stock movement
                movement = StockMovement(
                    stock_id=statement.id,
                    transaction_type=StockTransactionType.INDENT_DISPATCH,
                    quantity=item.approved_quantity,
                    direction=StockMovementDirection.OUT,
                    reference_type="INDENT",
                    reference_id=str(indent.id),
                    created_by=user_id
                )
                self.session.add(movement)
                
                # Update item state
                item.dispatched_quantity = item.approved_quantity
                
        indent.status = IndentStatus.DISPATCHED
        return self.indent_repo.update(indent)
