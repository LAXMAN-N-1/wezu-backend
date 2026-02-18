from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from typing import List
from app.api import deps
from app.core.audit import audit_log
from app.models.user import User
from app.models.financial import Transaction
from app.schemas.wallet import TransactionResponse, RechargeRequest
from app.schemas.payment import WalletBalanceResponse, PaymentMethodResponse
from app.services.wallet_service import WalletService
from app.services.payment_service import PaymentService
from app.services.invoice_service import InvoiceService
from fastapi.responses import StreamingResponse

router = APIRouter()

# Payment Methods
@router.get("/payment-methods", response_model=dict)
async def list_payment_methods(current_user: User = Depends(deps.get_current_user)):
    """List stored payment methods"""
    from app.api.v1.payments import get_payment_methods
    return get_payment_methods(current_user)

@router.post("/payment-methods")
async def add_payment_method(
    method_data: dict,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Add a new payment method"""
    return {"message": "Payment method added", "id": "new_method_id"}

@router.delete("/payment-methods/{method_id}")
async def remove_payment_method(
    method_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Remove a payment method"""
    return {"message": "Payment method removed"}

# Wallet
@router.get("/balance", response_model=WalletBalanceResponse)
@router.get("/", response_model=WalletBalanceResponse)
async def get_wallet_balance(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Current wallet balance and cashback balance"""
    wallet = WalletService.get_wallet(db, current_user.id)
    return {
        "user_id": current_user.id,
        "balance": wallet.balance,
        "cashback_balance": wallet.cashback_balance,
        "currency": wallet.currency
    }

@router.post("/recharge", response_model=dict)
@audit_log("WALLET_RECHARGE", "WALLET")
async def recharge_wallet(
    request: Request,
    recharge_in: RechargeRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Create order for wallet topup"""
    order = PaymentService.create_order(recharge_in.amount)
    return order

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_wallet_transactions(
    transaction_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Paginated wallet transaction history with filters"""
    wallet = WalletService.get_wallet(db, current_user.id)
    statement = select(Transaction).where(Transaction.wallet_id == wallet.id)
    if transaction_type:
        statement = statement.where(Transaction.transaction_type == transaction_type)
    if status:
        statement = statement.where(Transaction.status == status)
        
    return db.exec(statement.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)).all()

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
    payment_mode: str
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None

@router.post("/withdraw", response_model=dict) # Return basic dict or WithdrawalRequest model if schema defined
@audit_log("WALLET_WITHDRAWAL", "WALLET")
async def request_withdrawal(
    request: Request,
    req: WithdrawRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request withdrawal to bank account"""
    try:
        bank_details = {
            "payment_mode": req.payment_mode,
            "account_number": req.account_number,
            "account_holder_name": req.account_holder_name,
            "bank_name": req.bank_name,
            "ifsc_code": req.ifsc_code,
            "upi_id": req.upi_id
        }
        bank_details = {k: v for k, v in bank_details.items() if v is not None}
        
        wr = WalletService.request_withdrawal(db, current_user.id, req.amount, bank_details)
        return {"status": "success", "request_id": wr.id, "message": "Withdrawal request submitted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transactions/{payment_id}/receipt")
async def get_payment_receipt(
    payment_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Download PDF receipt for a transaction"""
    txn = db.get(Transaction, payment_id)
    if not txn or txn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Payment record not found")
    
    if txn.rental_id:
        return InvoiceService.generate_rental_invoice(txn.rental_id, db)
    
    raise HTTPException(status_code=400, detail="Receipt not available for this transaction type")

@router.get("/lookup")
async def lookup_user_by_phone(
    phone: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Lookup user by phone number to mask name before transfer"""
    user = db.exec(select(User).where(User.phone_number == phone)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Use full_name if first_name/last_name are missing
    full_name = user.full_name or ""
    parts = full_name.split()
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    
    if len(first_name) >= 3:
        masked_first = first_name[:3] + "***"
    elif len(first_name) > 0:
        masked_first = first_name[0] + "***"
    else:
        masked_first = "***"
        
    masked_name = f"{masked_first} {last_name[:1] + '.' if last_name else ''}".strip()
    return {"masked_name": masked_name}
