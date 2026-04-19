from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List
from app.api import deps
from app.models.user import User
from app.models.financial import Transaction
from app.schemas.wallet import TransactionResponse

router = APIRouter()

@router.get("/", response_model=List[TransactionResponse])
async def get_my_transactions(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 20,
):
    """
    Get current user's transaction history
    """
    query = select(Transaction).join(Transaction.wallet).where(Transaction.wallet.has(user_id=current_user.id)).offset(skip).limit(limit).order_by(Transaction.created_at.desc())
    return db.exec(query).all()

from app.models.invoice import Invoice
from app.services.financial_service import FinancialService
from fastapi import HTTPException

@router.get("/{id}/invoice", response_model=Invoice)
async def get_invoice(
    id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Verify transaction belongs to user
    txn = db.get(Transaction, id)
    if not txn or not txn.wallet or txn.wallet.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    # Find or Create Invoce
    # Check if invoice exists
    invoice = db.exec(select(Invoice).where(Invoice.transaction_id == id)).first()
    if not invoice:
        # Auto generate? Or return 404? 
        # Usually generated on completion. We can generate on fly if missing.
        invoice = FinancialService.create_invoice(db, id, current_user.id)
        
    return invoice
