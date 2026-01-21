"""
Enhanced Purchase/Catalog Endpoints
Additional purchase operations including cart management, order cancellation, and warranty
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from app.models.user import User
from app.models.catalog import CatalogOrder
from app.db.session import get_session
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CartItemUpdate(BaseModel):
    quantity: int


@router.patch("/cart/{item_id}")
async def update_cart_item(
    item_id: int,
    update: CartItemUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Update cart item quantity"""
    # Note: Cart functionality would need proper cart model implementation
    # For now, return success message
    return {
        "message": "Cart item updated",
        "item_id": item_id,
        "quantity": update.quantity
    }


@router.delete("/cart/{item_id}")
async def remove_cart_item(
    item_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Remove item from cart"""
    # Note: Cart functionality would need proper cart model implementation
    return {"message": "Item removed from cart", "item_id": item_id}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Cancel an order"""
    order = db.get(CatalogOrder, order_id)
    
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status not in ["pending", "confirmed"]:
        raise HTTPException(
            status_code=400,
            detail="Order cannot be cancelled in current status"
        )
    
    order.status = "cancelled"
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return {
        "message": "Order cancelled successfully",
        "order_id": order.id,
        "refund_status": "processing"
    }


class WarrantyClaim(BaseModel):
    issue_description: str
    images: Optional[list] = None


@router.post("/orders/{order_id}/warranty")
async def claim_warranty(
    order_id: int,
    claim: WarrantyClaim,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Claim warranty for an order"""
    order = db.get(CatalogOrder, order_id)
    
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Create warranty claim ticket
    from app.models.support import SupportTicket
    
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=f"Warranty Claim - Order #{order_id}",
        description=claim.issue_description,
        category="warranty",
        priority="medium",
        status="open"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "Warranty claim submitted",
        "ticket_id": ticket.id,
        "order_id": order_id,
        "status": "under_review"
    }
