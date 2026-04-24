from __future__ import annotations
"""
Enhanced Wallet Endpoints
Additional wallet operations including withdraw, cashback, and transfers
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import Optional
from app.api import deps
from app.models.user import User
from app.models.financial import Transaction, Wallet
from app.db.session import get_session
from app.repositories.wallet_repository import wallet_repository
from app.services.wallet_service import WalletService
from pydantic import BaseModel

router = APIRouter()


class WithdrawRequest(BaseModel):
    amount: float
    bank_account_id: str


class TransferRequest(BaseModel):
    recipient_phone: str
    amount: float
    note: Optional[str] = None


@router.post("/withdrawals")
def withdraw_from_wallet(
    request: WithdrawRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Enhanced withdraw flow without shadowing the base /withdraw route."""
    try:
        withdrawal = WalletService.request_withdrawal(
            db,
            current_user.id,
            request.amount,
            {"bank_account_id": request.bank_account_id},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    
    return {
        "message": "Withdrawal initiated",
        "transaction_id": withdrawal.id,
        "amount": request.amount,
        "status": "pending"
    }


@router.get("/cashback")
def get_cashback_history(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Get cashback history"""
    wallet = wallet_repository.get_by_user(db, current_user.id)
    if not wallet:
        return {"total_cashback": 0, "transactions": []}

    statement = (
        select(Transaction)
        .where(
            Transaction.wallet_id == wallet.id,
            Transaction.category == "cashback",
        )
        .order_by(Transaction.created_at.desc())
    )
    cashback_transactions = db.exec(statement).all()
    total_cashback = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.wallet_id == wallet.id,
            Transaction.category == "cashback",
        )
    ).one()
    
    return {
        "total_cashback": total_cashback,
        "transactions": cashback_transactions
    }


@router.post("/transfer")
def transfer_to_user(
    request: TransferRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Transfer money to another user"""
    amount_value = WalletService._to_money(request.amount)
    if amount_value <= 0:
        raise HTTPException(status_code=400, detail="Transfer amount must be greater than zero")
    
    # Find recipient
    statement = select(User).where(User.phone_number == request.recipient_phone)
    recipient = db.exec(statement).first()
    
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if not recipient.is_active or getattr(recipient, "is_deleted", False):
        raise HTTPException(status_code=400, detail="Recipient account is not active")
    
    if recipient.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself")
    
    try:
        # Lock wallets in deterministic order to prevent deadlocks under concurrent transfers.
        locked_wallets: dict[int, Wallet] = {}
        for user_id in sorted([current_user.id, recipient.id]):
            wallet = db.exec(
                select(Wallet).where(Wallet.user_id == user_id).with_for_update()
            ).first()
            if not wallet:
                wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
                db.add(wallet)
                db.flush()
            locked_wallets[user_id] = wallet

        sender_wallet = locked_wallets[current_user.id]
        recipient_wallet = locked_wallets[recipient.id]
        sender_balance = WalletService._to_money(sender_wallet.balance)
        recipient_balance = WalletService._to_money(recipient_wallet.balance)

        if sender_balance < amount_value:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        sender_wallet.balance = sender_balance - amount_value
        recipient_wallet.balance = recipient_balance + amount_value
        db.add(sender_wallet)
        db.add(recipient_wallet)

        sender_txn = Transaction(
            wallet_id=sender_wallet.id,
            amount=-amount_value,
            balance_after=WalletService._to_money(sender_wallet.balance),
            type="debit",
            category="transfer_out",
            status="success",
            description=request.note or f"Transfer to {recipient.phone_number or recipient.id}",
            reference_type="user_transfer",
            reference_id=str(recipient.id),
        )
        recipient_txn = Transaction(
            wallet_id=recipient_wallet.id,
            amount=amount_value,
            balance_after=WalletService._to_money(recipient_wallet.balance),
            type="credit",
            category="transfer_in",
            status="success",
            description=request.note or f"Transfer from {current_user.phone_number or current_user.id}",
            reference_type="user_transfer",
            reference_id=str(current_user.id),
        )
        db.add(sender_txn)
        db.add(recipient_txn)
        db.commit()
        db.refresh(sender_txn)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    
    return {
        "message": "Transfer successful",
        "amount": float(amount_value),
        "recipient": recipient.full_name,
        "transaction_id": sender_txn.id
    }
