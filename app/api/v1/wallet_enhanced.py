"""
Enhanced Wallet Endpoints
Additional wallet operations including withdraw, cashback, and transfers
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.models.financial import Wallet, Transaction
from app.db.session import get_session
from app.repositories.wallet_repository import wallet_repository
from pydantic import BaseModel

router = APIRouter()


class WithdrawRequest(BaseModel):
    amount: float
    bank_account_id: str


class TransferRequest(BaseModel):
    recipient_phone: str
    amount: float
    note: Optional[str] = None


@router.post("/withdraw")
async def withdraw_from_wallet(
    request: WithdrawRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Withdraw money from wallet to bank account"""
    wallet = wallet_repository.get_by_user(db, current_user.id)
    
    if not wallet or wallet.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Deduct from wallet
    wallet_repository.deduct_balance(db, current_user.id, request.amount)
    
    # Create withdrawal transaction
    transaction = Transaction(
        user_id=current_user.id,
        amount=request.amount,
        transaction_type="withdrawal",
        status="pending",
        payment_method="bank_transfer"
    )
    db.add(transaction)
    db.commit()
    
    return {
        "message": "Withdrawal initiated",
        "transaction_id": transaction.id,
        "amount": request.amount,
        "status": "pending"
    }


@router.get("/cashback")
async def get_cashback_history(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Get cashback history"""
    from sqlmodel import select
    statement = select(Transaction).where(
        (Transaction.user_id == current_user.id) &
        (Transaction.transaction_type == "cashback")
    )
    cashback_transactions = db.exec(statement).all()
    
    total_cashback = sum(t.amount for t in cashback_transactions)
    
    return {
        "total_cashback": total_cashback,
        "transactions": cashback_transactions
    }


@router.post("/transfer")
async def transfer_to_user(
    request: TransferRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Transfer money to another user"""
    from sqlmodel import select
    
    # Check sender balance
    sender_wallet = wallet_repository.get_by_user(db, current_user.id)
    if not sender_wallet or sender_wallet.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Find recipient
    statement = select(User).where(User.phone_number == request.recipient_phone)
    recipient = db.exec(statement).first()
    
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    if recipient.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself")
    
    # Deduct from sender
    wallet_repository.deduct_balance(db, current_user.id, request.amount)
    
    # Add to recipient
    wallet_repository.add_balance(db, recipient.id, request.amount)
    
    # Create transaction records
    sender_txn = Transaction(
        user_id=current_user.id,
        amount=request.amount,
        transaction_type="transfer_out",
        status="completed",
        payment_method="wallet"
    )
    recipient_txn = Transaction(
        user_id=recipient.id,
        amount=request.amount,
        transaction_type="transfer_in",
        status="completed",
        payment_method="wallet"
    )
    
    db.add(sender_txn)
    db.add(recipient_txn)
    db.commit()
    
    return {
        "message": "Transfer successful",
        "amount": request.amount,
        "recipient": recipient.full_name,
        "transaction_id": sender_txn.id
    }
