from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.models.financial import Transaction
from app.models.invoice import Invoice
from app.schemas.wallet import TransactionResponse, DealerTransactionResponse, TransactionLifecycleResponse
from app.services.financial_service import FinancialService

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

@router.get("/dealer", response_model=List[DealerTransactionResponse])
async def get_dealer_transactions(
    query: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    types: Optional[List[str]] = Query(None),
    statuses: Optional[List[str]] = Query(None),
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    station_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Get dealer's transaction history with advanced filtering
    """
    return FinancialService.search_dealer_transactions(
        db, current_user.id, query, start_date, end_date, types, statuses, min_amount, max_amount, station_id, skip, limit
    )

@router.get("/{id}/lifecycle", response_model=TransactionLifecycleResponse)
async def get_transaction_lifecycle(
    id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Get lifecycle timeline for a specific transaction
    """
    events = FinancialService.get_transaction_lifecycle(db, id)
    return {"transaction_id": id, "events": events}

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
        invoice = FinancialService.create_invoice(id, current_user.id)
        
    return invoice
