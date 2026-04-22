from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import Any, List, Optional
from pydantic import BaseModel, Field
import logging

from app.api import deps
from app.core.audit import audit_log

logger = logging.getLogger(__name__)
from app.models.user import User
from app.models.financial import Transaction
from app.schemas.wallet import TransactionResponse, RechargeRequest
from app.schemas.payment import WalletBalanceResponse
from app.services.wallet_service import WalletService
from app.services.payment_service import PaymentService
from app.services.payment_method_service import PaymentMethodService
from app.services.invoice_service import InvoiceService
from fastapi.responses import StreamingResponse

router = APIRouter()


class PaymentMethodCreateRequest(BaseModel):
    type: str
    provider_token: str
    provider: str = "razorpay"
    is_default: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


# Payment Methods
@router.get("/payment-methods", response_model=dict)
async def list_payment_methods(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """List stored payment methods"""
    methods = PaymentMethodService.list_serialized_methods(db, current_user.id)
    default_method_id = next((item["id"] for item in methods if item.get("is_default")), None)
    return {
        "success": True,
        "data": {
            "methods": methods,
            "available_methods": PaymentMethodService.available_method_catalog(),
            "default_method_id": default_method_id,
        },
    }

@router.post("/payment-methods")
async def add_payment_method(
    method_data: PaymentMethodCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Add a new payment method"""
    method, created = PaymentMethodService.add_method(
        db,
        user_id=current_user.id,
        method_type=method_data.type,
        provider_token=method_data.provider_token,
        provider=method_data.provider,
        is_default=method_data.is_default,
        details=method_data.details,
    )
    return {
        "success": True,
        "message": "Payment method added" if created else "Payment method already exists",
        "created": created,
        "method": PaymentMethodService.serialize(method),
    }

@router.delete("/payment-methods/{method_id}")
async def remove_payment_method(
    method_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Remove a payment method"""
    PaymentMethodService.delete_method(db, user_id=current_user.id, method_id=method_id)
    return {"success": True, "message": "Payment method removed", "method_id": method_id}

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

# DECONFLICTED P0-B: POST /transfer removed.
# Canonical handler lives in app/api/v1/wallet_enhanced.py.
# Legacy handler called WalletService.transfer_balance() which does not exist.
# Removed 2026-04-06.

# DECONFLICTED P0-B: GET /cashback removed.
# Canonical handler lives in app/api/v1/wallet_enhanced.py.
# Legacy handler called WalletService.get_cashback_history() which does not exist.
# Removed 2026-04-06.

class WithdrawRequest(BaseModel):
    amount: float
    payment_mode: str
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None


class WalletPayRequest(BaseModel):
    amount: float
    description: Optional[str] = None

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
        logger.exception("withdrawal_request_failed", user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Withdrawal request failed")


@router.post("/pay", response_model=dict)
@audit_log("WALLET_PAYMENT", "WALLET")
async def pay_from_wallet(
    request: Request,
    req: WalletPayRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Deduct amount from wallet for direct in-app payment flows.
    """
    try:
        wallet = WalletService.deduct_balance(
            db,
            current_user.id,
            req.amount,
            description=req.description or "Wallet payment",
        )
        return {
            "status": "success",
            "balance": float(wallet.balance),
            "message": "Payment successful",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("wallet_payment_failed", user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Wallet payment failed")

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
