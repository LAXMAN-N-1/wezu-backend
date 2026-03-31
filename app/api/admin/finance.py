from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, col
from typing import List, Optional
from datetime import datetime, UTC, timedelta
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.financial import Transaction, WalletWithdrawalRequest, TransactionType, TransactionStatus
from app.models.refund import Refund
from app.models.invoice import Invoice
from app.models.settlement import Settlement

router = APIRouter()

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_finance_dashboard(
    period: str = Query("30d", description="7d, 30d, 90d, 1y"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Revenue dashboard with aggregated financial metrics."""
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(period, 30)
    since = datetime.now(UTC) - timedelta(days=days)
    prev_since = since - timedelta(days=days)

    # Current period revenue
    current_rev = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= since)
    ).one()

    # Previous period revenue for growth calc
    prev_rev = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= prev_since, Transaction.created_at < since)
    ).one()

    growth = round(((current_rev - prev_rev) / prev_rev * 100) if prev_rev > 0 else 0, 1)

    # Total all-time
    total_rev = db.exec(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.status == TransactionStatus.SUCCESS)).one()

    # Revenue by type
    grouped = db.exec(
        select(Transaction.transaction_type, func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= since)
        .group_by(Transaction.transaction_type)
    ).all()
    type_breakdown = [{"type": t.value if hasattr(t, "value") else str(t), "amount": round(a, 2)} for t, a in grouped if a > 0]

    # Monthly revenue chart (last 6 months)
    start_6m = datetime.now(UTC).replace(day=1) - timedelta(days=30 * 5)
    all_recent_tx = db.exec(
        select(Transaction.amount, Transaction.created_at)
        .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= start_6m)
    ).all()
    
    chart_data = []
    for i in range(5, -1, -1):
        m_start = datetime.now(UTC).replace(day=1) - timedelta(days=30 * i)
        m_end = m_start + timedelta(days=30)
        m_rev = sum(tx.amount for tx in all_recent_tx if tx.created_at and m_start <= tx.created_at.replace(tzinfo=UTC) < m_end)
        chart_data.append({"month": m_start.strftime("%b"), "value": round(m_rev, 2)})

    # Recent transactions
    recent = db.exec(select(Transaction).order_by(Transaction.created_at.desc()).limit(10)).all()
    user_ids = {tx.user_id for tx in recent if tx.user_id}
    user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    recent_list = []
    for tx in recent:
        user = user_map.get(tx.user_id)
        recent_list.append({
            "id": f"TXN_{tx.id}",
            "user_id": f"USER_{tx.user_id}",
            "user_name": user.full_name if user else "Unknown",
            "amount": tx.amount,
            "type": tx.transaction_type.value if hasattr(tx.transaction_type, 'value') else str(tx.transaction_type),
            "status": tx.status.value if hasattr(tx.status, 'value') else str(tx.status),
            "timestamp": tx.created_at.isoformat(),
        })

    return {
        "total_revenue": round(total_rev, 2),
        "period_revenue": round(current_rev, 2),
        "monthly_growth": growth,
        "revenue_chart": chart_data,
        "revenue_by_type": type_breakdown,
        "recent_transactions": recent_list,
        "total_transactions": db.exec(select(func.count(Transaction.id))).one(),
        "success_rate": round(
            db.exec(select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.SUCCESS)).one()
            / max(db.exec(select(func.count(Transaction.id))).one(), 1) * 100, 1
        ),
    }


# ─── TRANSACTIONS ─────────────────────────────────────────────────────────────

@router.get("/transactions")
def list_transactions(
    skip: int = 0, limit: int = 100,
    type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List all financial transactions with filters."""
    statement = select(Transaction)
    if type:
        statement = statement.where(Transaction.transaction_type == type)
    if status:
        statement = statement.where(Transaction.status == status)
    
    total = db.exec(select(func.count(Transaction.id))).one()
    statement = statement.offset(skip).limit(limit).order_by(Transaction.created_at.desc())
    txns = db.exec(statement).all()

    user_ids = {tx.user_id for tx in txns if tx.user_id}
    user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    result = []
    for tx in txns:
        user = user_map.get(tx.user_id)
        result.append({
            "id": tx.id,
            "user_id": tx.user_id,
            "user_name": user.full_name if user else "Unknown",
            "amount": tx.amount,
            "tax_amount": tx.tax_amount,
            "currency": tx.currency,
            "transaction_type": tx.transaction_type.value if hasattr(tx.transaction_type, 'value') else str(tx.transaction_type),
            "status": tx.status.value if hasattr(tx.status, 'value') else str(tx.status),
            "payment_method": tx.payment_method,
            "payment_gateway_ref": tx.payment_gateway_ref,
            "description": tx.description,
            "created_at": tx.created_at.isoformat(),
        })
    return {"transactions": result, "total_count": total}

@router.get("/transactions/stats")
def get_transaction_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Transaction aggregation stats."""
    total = db.exec(select(func.count(Transaction.id))).one()
    success = db.exec(select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.SUCCESS)).one()
    pending = db.exec(select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.PENDING)).one()
    failed = db.exec(select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.FAILED)).one()
    total_amount = db.exec(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.status == TransactionStatus.SUCCESS)).one()
    today_amount = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= datetime.now(UTC).replace(hour=0, minute=0, second=0))
    ).one()

    return {
        "total_transactions": total,
        "success_count": success,
        "pending_count": pending,
        "failed_count": failed,
        "total_amount": round(total_amount, 2),
        "today_amount": round(today_amount, 2),
    }


# ─── SETTLEMENTS ──────────────────────────────────────────────────────────────

@router.get("/settlements")
def list_settlements(
    skip: int = 0, limit: int = 50,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """List dealer/vendor settlements."""
    statement = select(Settlement)
    if status:
        statement = statement.where(Settlement.status == status)
    
    total = db.exec(select(func.count(Settlement.id))).one()
    settlements = db.exec(statement.offset(skip).limit(limit).order_by(Settlement.created_at.desc())).all()

    from app.models.dealer import DealerProfile
    dealer_ids = {s.dealer_id for s in settlements if s.dealer_id}
    dealer_map = {d.user_id: d for d in db.exec(select(DealerProfile).where(DealerProfile.user_id.in_(dealer_ids))).all()} if dealer_ids else {}

    result = []
    for s in settlements:
        dealer = dealer_map.get(s.dealer_id)
        dealer_name = dealer.business_name if dealer else "N/A"
        result.append({
            "id": s.id,
            "dealer_id": s.dealer_id,
            "dealer_name": dealer_name,
            "settlement_month": s.settlement_month,
            "total_revenue": s.total_revenue,
            "total_commission": s.total_commission,
            "platform_fee": s.platform_fee,
            "tax_amount": s.tax_amount,
            "net_payable": s.net_payable,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
            "paid_at": s.paid_at.isoformat() if s.paid_at else None,
        })
    return {"settlements": result, "total_count": total}

@router.get("/settlements/stats")
def get_settlement_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    total = db.exec(select(func.count(Settlement.id))).one()
    pending = db.exec(select(func.count(Settlement.id)).where(Settlement.status == "pending")).one()
    paid = db.exec(select(func.count(Settlement.id)).where(Settlement.status == "paid")).one()
    total_payable = db.exec(select(func.coalesce(func.sum(Settlement.net_payable), 0))).one()
    total_paid = db.exec(select(func.coalesce(func.sum(Settlement.net_payable), 0)).where(Settlement.status == "paid")).one()

    return {
        "total_settlements": total,
        "pending_count": pending,
        "paid_count": paid,
        "total_payable": round(total_payable, 2),
        "total_paid": round(total_paid, 2),
    }

@router.put("/settlements/{settlement_id}/approve")
def approve_settlement(
    settlement_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    s = db.get(Settlement, settlement_id)
    if not s:
        raise HTTPException(404, "Settlement not found")
    s.status = "approved"
    db.add(s)
    db.commit()
    return {"status": "success"}


# ─── INVOICES ─────────────────────────────────────────────────────────────────

@router.get("/invoices")
def list_invoices(
    skip: int = 0, limit: int = 50,
    search: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    statement = select(Invoice)
    if search:
        statement = statement.where(Invoice.invoice_number.contains(search))

    total = db.exec(select(func.count(Invoice.id))).one()
    invoices = db.exec(statement.offset(skip).limit(limit).order_by(Invoice.created_at.desc())).all()

    user_ids = {i.user_id for i in invoices if i.user_id}
    user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    result = []
    for inv in invoices:
        user = user_map.get(inv.user_id)
        result.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "user_id": inv.user_id,
            "user_name": user.full_name if user else "Unknown",
            "amount": inv.amount,
            "subtotal": inv.subtotal,
            "tax_amount": inv.tax_amount,
            "total": inv.total,
            "gstin": inv.gstin,
            "pdf_url": inv.pdf_url,
            "is_late_fee": inv.is_late_fee,
            "created_at": inv.created_at.isoformat(),
        })
    return {"invoices": result, "total_count": total}

@router.get("/invoices/stats")
def get_invoice_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    total = db.exec(select(func.count(Invoice.id))).one()
    total_amount = db.exec(select(func.coalesce(func.sum(Invoice.total), 0))).one()
    total_tax = db.exec(select(func.coalesce(func.sum(Invoice.tax_amount), 0))).one()

    return {
        "total_invoices": total,
        "total_amount": round(total_amount, 2),
        "total_tax_collected": round(total_tax, 2),
    }


# ─── PROFIT ANALYSIS ─────────────────────────────────────────────────────────

@router.get("/profit/analysis")
def get_profit_analysis(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Profit analysis with revenue, costs, and margins."""
    total_revenue = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS)
    ).one()

    total_commissions = db.exec(
        select(func.coalesce(func.sum(Settlement.total_commission), 0))
    ).one()

    total_platform_fees = db.exec(
        select(func.coalesce(func.sum(Settlement.platform_fee), 0))
    ).one()

    total_refunds = db.exec(
        select(func.coalesce(func.sum(Refund.amount), 0))
    ).one()

    total_tax = db.exec(
        select(func.coalesce(func.sum(Transaction.tax_amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS)
    ).one()

    gross_profit = total_revenue - total_commissions - total_refunds
    net_profit = gross_profit - total_platform_fees
    margin = round((net_profit / total_revenue * 100) if total_revenue > 0 else 0, 1)

    # Monthly trend
    start_6m = datetime.now(UTC).replace(day=1) - timedelta(days=30 * 5)
    all_recent_tx = db.exec(
        select(Transaction.amount, Transaction.created_at)
        .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= start_6m)
    ).all()
    all_recent_settle = db.exec(
        select(Settlement.total_commission, Settlement.created_at)
        .where(Settlement.created_at >= start_6m)
    ).all()
    
    monthly_trend = []
    for i in range(5, -1, -1):
        m_start = datetime.now(UTC).replace(day=1) - timedelta(days=30 * i)
        m_end = m_start + timedelta(days=30)
        m_rev = sum(tx.amount for tx in all_recent_tx if tx.created_at and m_start <= tx.created_at.replace(tzinfo=UTC) < m_end)
        m_comm = sum(s.total_commission for s in all_recent_settle if s.created_at and m_start <= s.created_at.replace(tzinfo=UTC) < m_end)
        monthly_trend.append({
            "month": m_start.strftime("%b %Y"),
            "revenue": round(m_rev, 2),
            "costs": round(m_comm, 2),
            "profit": round(m_rev - m_comm, 2),
        })

    # Revenue by transaction type for pie chart
    grouped = db.exec(
        select(Transaction.transaction_type, func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == TransactionStatus.SUCCESS)
        .group_by(Transaction.transaction_type)
    ).all()
    type_data = [{"type": t.value if hasattr(t, "value") else str(t), "amount": round(a, 2)} for t, a in grouped if a > 0]

    return {
        "total_revenue": round(total_revenue, 2),
        "total_commissions": round(total_commissions, 2),
        "total_refunds": round(total_refunds, 2),
        "total_platform_fees": round(total_platform_fees, 2),
        "total_tax_collected": round(total_tax, 2),
        "gross_profit": round(gross_profit, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin": margin,
        "monthly_trend": monthly_trend,
        "revenue_by_type": type_data,
    }


# ─── WITHDRAWALS ──────────────────────────────────────────────────────────────

@router.get("/withdrawals")
def list_withdrawal_requests(
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    statement = select(WalletWithdrawalRequest)
    if status:
        statement = statement.where(WalletWithdrawalRequest.status == status)
    requests = db.exec(statement.order_by(WalletWithdrawalRequest.created_at.desc())).all()
    return requests

@router.put("/withdrawals/{request_id}/approve")
def approve_withdrawal(
    request_id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    req = db.get(WalletWithdrawalRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "requested":
        raise HTTPException(status_code=400, detail="Request already processed")
    req.status = "approved"
    db.add(req)
    db.commit()
    return {"status": "success", "message": "Withdrawal request approved"}

@router.post("/refunds")
def initiate_refund(
    transaction_id: int,
    amount: float,
    reason: str,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    tx = db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    existing_refund = db.exec(select(Refund).where(Refund.transaction_id == tx.id)).first()
    if existing_refund:
        raise HTTPException(status_code=400, detail="Transaction already has a refund record")
    refund = Refund(transaction_id=tx.id, amount=amount, reason=reason, status="pending")
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund
