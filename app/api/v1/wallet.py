from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.models.financial import Transaction
from app.schemas.wallet import WalletResponse, TransactionResponse, RechargeRequest
from app.services.wallet_service import WalletService
from app.services.payment_service import PaymentService

router = APIRouter()

@router.get("/", response_model=WalletResponse)
async def get_wallet(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return WalletService.get_wallet(db, current_user.id)

@router.post("/recharge", response_model=dict)
async def recharge_wallet(
    recharge_in: RechargeRequest,
    current_user: User = Depends(deps.get_current_user),
):
    # Create order in Razorpay
    order = PaymentService.create_order(recharge_in.amount)
    return order # Returns Razorpay order details for frontend

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    wallet = WalletService.get_wallet(db, current_user.id)
    # Simple query
    from sqlmodel import select
    return db.exec(select(Transaction).where(Transaction.wallet_id == wallet.id).order_by(Transaction.created_at.desc())).all()

from pydantic import BaseModel
class TransferRequest(BaseModel):
    recipient_phone: str
    amount: float
    note: Optional[str] = None

@router.post("/transfer", response_model=TransactionResponse)
async def transfer_to_user(
    request: TransferRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Transfer money to another user by phone number"""
    return WalletService.transfer_balance(
        db, 
        sender_id=current_user.id, 
        recipient_phone=request.recipient_phone, 
        amount=request.amount, 
        note=request.note
    )

@router.get("/cashback")
async def get_cashback_history(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Get cashback history and total"""
    transactions = WalletService.get_cashback_history(db, current_user.id)
    total_cashback = sum(t.amount for t in transactions)
    
    return {
        "total_cashback": total_cashback,
        "transactions": transactions
    }

class WithdrawRequest(BaseModel):
    amount: float
    bank_details: dict

@router.post("/withdraw", response_model=dict) # Return basic dict or WithdrawalRequest model if schema defined
async def request_withdrawal(
    req: WithdrawRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    try:
        wr = WalletService.request_withdrawal(db, current_user.id, req.amount, req.bank_details)
        return {"status": "success", "request_id": wr.id, "message": "Withdrawal request submitted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
