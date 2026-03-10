from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.financial import Transaction, WalletWithdrawalRequest
from app.models.refund import Refund

router = APIRouter()

@router.get("/transactions")
def list_transactions(
    skip: int = 0,
    limit: int = 100,
    type: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """List all financial transactions."""
    statement = select(Transaction)
    if type:
        statement = statement.where(Transaction.transaction_type == type)
    
    statement = statement.offset(skip).limit(limit).order_by(Transaction.created_at.desc())
    transactions = db.exec(statement).all()
    return transactions

@router.get("/withdrawals")
def list_withdrawal_requests(
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """List wallet withdrawal requests (e.g., from vendors)."""
    statement = select(WalletWithdrawalRequest)
    if status:
        statement = statement.where(WalletWithdrawalRequest.status == status)
    
    requests = db.exec(statement.order_by(WalletWithdrawalRequest.created_at.desc())).all()
    return requests

@router.put("/withdrawals/{request_id}/approve")
def approve_withdrawal(
    request_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Approve a withdrawal request."""
    req = db.get(WalletWithdrawalRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if req.status != "requested":
        raise HTTPException(status_code=400, detail="Request already processed")
    
    req.status = "approved"
    # Actual money transfer logic would initiate here
    db.add(req)
    db.commit()
    return {"status": "success", "message": "Withdrawal request approved"}

@router.post("/refunds")
def initiate_refund(
    transaction_id: int,
    amount: float,
    reason: str,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Initiate a refund for a transaction."""
    tx = db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Check if already refunded
    existing_refund = db.exec(select(Refund).where(Refund.transaction_id == tx.id)).first()
    if existing_refund:
        raise HTTPException(status_code=400, detail="Transaction already has a refund record")

    refund = Refund(
        transaction_id=tx.id,
        amount=amount,
        reason=reason,
        status="pending"
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    # Integration with Razorpay refund API would go here
    return refund
