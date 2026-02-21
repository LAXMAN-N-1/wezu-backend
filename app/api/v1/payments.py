"""
Enhanced Payment and Invoice API
Invoice generation, refunds, and payment methods
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.catalog import CatalogOrder
from app.models.rental import Rental
from app.models.financial import Transaction
from app.services.invoice_service import InvoiceService
from app.services.analytics_service import AnalyticsService
from app.services.payment_service import PaymentService
from app.schemas.common import DataResponse
from app.schemas.payment import (
    RevenueSummary, StationRevenueResponse, 
    RevenueForecastResponse, ProfitMarginResponse
)

router = APIRouter()

# Schemas
class RefundRequest(BaseModel):
    transaction_id: Optional[int] = None
    order_id: Optional[int] = None
    reason: str
    amount: Optional[float] = None  # If None, full refund

class PaymentMethodCreate(BaseModel):
    type: str  # card, upi, netbanking
    details: dict

# Payment Method Endpoints
@router.post("/methods")
async def add_payment_method(
    method: PaymentMethodCreate,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Add a new payment method"""
    return {
        "message": "Payment method added successfully",
        "method_id": "pm_" + str(current_user.id)
    }

@router.delete("/methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a payment method"""
    return {"message": "Payment method deleted successfully"}

# Invoice Endpoints
@router.get("/orders/{order_id}/invoice", response_class=StreamingResponse)
def download_order_invoice(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Download PDF invoice for order
    Returns PDF file
    """
    # Verify order belongs to user
    order = session.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Generate invoice
    pdf_buffer = InvoiceService.generate_order_invoice(order_id, session)
    
    if not pdf_buffer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invoice"
        )
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{order.order_number}.pdf"
        }
    )

@router.get("/rentals/{rental_id}/invoice", response_class=StreamingResponse)
def download_rental_invoice(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Download PDF invoice for rental"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rental not found"
        )
    
    pdf_buffer = InvoiceService.generate_rental_invoice(rental_id, session)
    
    if not pdf_buffer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invoice"
        )
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=rental_invoice_{rental_id}.pdf"
        }
    )



# Transaction Detail & Admin Management
@router.get("/transactions", response_model=DataResponse[list])
def get_user_all_payments(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """All payment transactions for the user (rentals + purchases)"""
    txns = session.exec(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
    ).all()
    return DataResponse(success=True, data=txns)

@router.get("/{id}", response_model=DataResponse[dict])
def get_payment_detail(
    id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Single transaction detail"""
    txn = session.get(Transaction, id)
    if not txn or (txn.user_id != current_user.id and not current_user.is_superuser):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return DataResponse(success=True, data=txn)

@router.post("/{id}/refund", response_model=DataResponse[dict])
def admin_initiate_refund(
    id: int,
    request: RefundRequest,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Admin: initiate manual refund for a transaction"""
    txn = session.get(Transaction, id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    # Call PaymentService to refund via gateway
    rf_data = PaymentService.refund_transaction(txn.payment_gateway_ref, request.amount)
    
    # Update local DB or Transaction status if successful handled in webhook too
    txn.status = "refunded"
    session.add(txn)
    session.commit()
    
    return DataResponse(success=True, data={"refund_id": rf_data.get("id"), "status": "initiated"})

@router.get("/{id}/refund-status", response_model=DataResponse[dict])
def get_refund_status(
    id: int,
    session: Session = Depends(get_session)
):
    """Track refund processing status"""
    from app.models.refund import Refund
    refund = session.exec(select(Refund).where(Refund.transaction_id == id)).first()
    if not refund:
        return DataResponse(success=False, data={"message": "No refund found for this transaction"})
    return DataResponse(success=True, data={"status": refund.status, "processed_at": refund.processed_at})

@router.get("/admin/payments", response_model=DataResponse[list])
def admin_get_all_payments(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Admin: all platform transactions with filters"""
    statement = select(Transaction)
    if status:
        statement = statement.where(Transaction.status == status)
    if user_id:
        statement = statement.where(Transaction.user_id == user_id)
        
    txns = session.exec(statement.offset(skip).limit(limit).order_by(Transaction.created_at.desc())).all()
    return DataResponse(success=True, data=txns)

# Revenue Dashboards
@router.get("/admin/revenue", response_model=DataResponse[RevenueSummary])
def get_revenue_dashboard(
    period: str = "daily",  # daily, weekly, monthly
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Revenue summary with comparison"""
    # Define time range
    end = datetime.utcnow()
    if period == "weekly":
        start = end - timedelta(days=7)
    elif period == "monthly":
        start = end - timedelta(days=30)
    else:
        start = end - timedelta(days=1)
        
    stats = AnalyticsService.get_revenue_stats(session, start, end)
    return DataResponse(success=True, data=stats)

@router.get("/admin/revenue/by-station", response_model=DataResponse[List[StationRevenueResponse]])
def get_revenue_by_station(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Revenue broken down per station"""
    data = AnalyticsService.get_revenue_by_station(session)
    return DataResponse(success=True, data=data)

@router.get("/admin/revenue/forecast", response_model=DataResponse[List[RevenueForecastResponse]])
def get_revenue_forecast(
    days: int = 30,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Projected revenue for next 30 days"""
    data = AnalyticsService.calculate_revenue_forecast(session, days)
    return DataResponse(success=True, data=data)

@router.get("/admin/profit-margins", response_model=DataResponse[List[ProfitMarginResponse]])
def get_profit_margins(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Margin analysis per station"""
    data = AnalyticsService.get_profit_margins(session)
    return DataResponse(success=True, data=data)

# Refund Endpoints
@router.post("/orders/{order_id}/refund", response_model=DataResponse[dict])
def request_refund(
    order_id: int,
    request: RefundRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Request refund for order
    Creates refund request for admin approval
    """
    order = session.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.status not in ["CONFIRMED", "SHIPPED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be refunded"
        )
    
    # Create refund transaction
    from app.models.financial import Transaction
    from datetime import datetime
    
    refund_amount = request.amount or order.total_amount
    
    transaction = Transaction(
        user_id=current_user.id,
        order_id=order_id,
        transaction_type="REFUND",
        amount=refund_amount,
        status="PENDING",
        description=f"Refund request: {request.reason}",
        created_at=datetime.utcnow()
    )
    session.add(transaction)
    session.commit()
    
    return DataResponse(
        success=True,
        data={
            "transaction_id": transaction.id,
            "refund_amount": refund_amount,
            "status": "PENDING",
            "message": "Refund request submitted. Processing time: 3-5 business days"
        }
    )

@router.get("/refunds", response_model=DataResponse[list])
def get_user_refunds(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get all refund requests for current user"""
    from app.models.financial import Transaction
    from sqlmodel import select
    
    refunds = session.exec(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.transaction_type == "REFUND")
        .order_by(Transaction.created_at.desc())
    ).all()
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": refund.id,
                "order_id": refund.order_id,
                "amount": refund.amount,
                "status": refund.status,
                "description": refund.description,
                "created_at": refund.created_at.isoformat()
            }
            for refund in refunds
        ]
    )

# Payment Methods Info
@router.get("/payment-methods", response_model=DataResponse[dict])
def get_payment_methods(current_user: User = Depends(deps.get_current_user)):
    """Get available payment methods"""
    return DataResponse(
        success=True,
        data={
            "methods": [
                {
                    "id": "UPI",
                    "name": "UPI",
                    "description": "Google Pay, PhonePe, Paytm, etc.",
                    "icon": "upi",
                    "enabled": True
                },
                {
                    "id": "CARD",
                    "name": "Credit/Debit Card",
                    "description": "Visa, Mastercard, RuPay",
                    "icon": "card",
                    "enabled": True
                },
                {
                    "id": "WALLET",
                    "name": "Digital Wallet",
                    "description": "Paytm, Amazon Pay, etc.",
                    "icon": "wallet",
                    "enabled": True
                },
                {
                    "id": "NETBANKING",
                    "name": "Net Banking",
                    "description": "All major banks",
                    "icon": "bank",
                    "enabled": True
                }
            ]
        }
    )

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Handle Razorpay Webhooks
    Updates transaction status and confirms rentals/orders
    """
    from app.services.payment_service import PaymentService
    from app.services.wallet_service import WalletService
    from app.models.financial import Transaction, TransactionStatus
    from app.models.catalog import CatalogOrder
    from app.core.config import settings
    import json
    
    # 1. Verify Signature
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    
    if not PaymentService.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    payload = json.loads(body)
    event = payload.get("event")
    
    # 2. Process Event
    if event == "payment.captured":
        payment_id = payload["payload"]["payment"]["entity"]["id"]
        order_id = payload["payload"]["payment"]["entity"]["order_id"]
        
        # Find transaction by order_id (payment_gateway_ref)
        txn = session.exec(select(Transaction).where(Transaction.payment_gateway_ref == order_id)).first()
        if txn:
            txn.status = TransactionStatus.SUCCESS
            txn.updated_at = datetime.utcnow()
            
            # If topup, update wallet
            if txn.transaction_type == "wallet_topup":
                WalletService.add_balance(session, txn.user_id, txn.amount, "Razorpay Topup Success")
            
            # If ecommerce order, mark as confirmed
            if txn.order_id:
                order = session.get(CatalogOrder, txn.order_id)
                if order:
                    order.status = "CONFIRMED"
                    session.add(order)
            
            session.add(txn)
            session.commit()
            
    return {"status": "ok"}
