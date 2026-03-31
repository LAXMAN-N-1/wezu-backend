from sqlmodel import Session
from fastapi import HTTPException
from app.models.grn import GRN, GRNItem, GRNStatus
from app.models.indent import IndentStatus
from app.repositories.grn_repository import GRNRepository
from app.repositories.indent_repository import IndentRepository
from app.schemas.grn import GRNCreate
from app.models.dealer_inventory import DealerInventory, InventoryTransaction


class GRNService:
    def __init__(self, session: Session):
        self.session = session
        self.grn_repo = GRNRepository(session)
        self.indent_repo = IndentRepository(session)
        
    def receive_grn(self, dealer_id: int, indent_id: int, grn_data: GRNCreate, user_id: int) -> GRN:
        indent = self.indent_repo.get_by_id(indent_id)
        if not indent:
            raise HTTPException(status_code=404, detail="Indent not found")
            
        if indent.dealer_id != dealer_id:
            raise HTTPException(status_code=403, detail="Not authorized to receive this indent")
            
        if indent.status != IndentStatus.DISPATCHED:
            raise HTTPException(status_code=400, detail="Indent is not in DISPATCHED state")
            
        grn = GRN(
            indent_id=indent.id,
            dealer_id=dealer_id,
            warehouse_id=indent.warehouse_id,
            status=GRNStatus.RECEIVED,
            received_by=user_id,
            notes=grn_data.notes
        )
        
        items_map = {item.id: item for item in indent.items}
        
        all_discrepancy = False
        
        for item_data in grn_data.items:
            indent_item = items_map.get(item_data.indent_item_id)
            if not indent_item:
                continue
                
            grn_item = GRNItem(
                indent_item_id=indent_item.id,
                product_id=indent_item.product_id,
                expected_quantity=indent_item.dispatched_quantity,
                received_quantity=item_data.received_quantity,
                damaged_quantity=item_data.damaged_quantity
            )
            grn.items.append(grn_item)
            
            # Update indent item
            indent_item.received_quantity = item_data.received_quantity
            
            if item_data.received_quantity != indent_item.dispatched_quantity:
                all_discrepancy = True
                
            # Increase Station / Dealer Stock natively
            # We assume dealer inventory or station stock is updated
            # For simplicity let's update dealer_inventory
            dealer_inv = self.session.query(DealerInventory).filter(
                DealerInventory.dealer_id == dealer_id,
                DealerInventory.product_id == indent_item.product_id
            ).first()
            
            if not dealer_inv:
                dealer_inv = DealerInventory(
                    dealer_id=dealer_id,
                    product_id=indent_item.product_id,
                    quantity_available=item_data.received_quantity
                )
                self.session.add(dealer_inv)
            else:
                dealer_inv.quantity_available += item_data.received_quantity
                self.session.add(dealer_inv)
                
            self.session.flush() # Ensure dealer_inv has an id
            
            # Record inventory transaction
            transaction = InventoryTransaction(
                inventory_id=dealer_inv.id,
                transaction_type="RECEIVED",
                quantity=item_data.received_quantity,
                reference_type="INDENT",
                reference_id=indent.id,
                notes=f"Received via GRN",
                performed_by=user_id
            )
            self.session.add(transaction)
            
        if all_discrepancy:
            grn.status = GRNStatus.DISCREPANCY
            indent.status = IndentStatus.PARTIAL_FULFILLED
        else:
            indent.status = IndentStatus.FULFILLED
            
        self.session.add(indent)
        return self.grn_repo.create_grn(grn)
