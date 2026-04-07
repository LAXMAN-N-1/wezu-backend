from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, col, case
from typing import List, Optional
from datetime import datetime, UTC, timedelta
from app.api import deps
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.financial import Transaction, WalletWithdrawalRequest, TransactionType, TransactionStatus
from app.models.refund import Refund
from app.models.invoice import Invoice
from app.models.settlement import Settlement
from app.utils.runtime_cache import cached_call

router = APIRouter()

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_finance_dashboard(
    period: str = Query("30d", description="7d, 30d, 90d, 1y"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Revenue dashboard with aggregated financial metrics."""
    _NS = "admin-finance"

    def _load():
        days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(period, 30)
        since = datetime.now(UTC) - timedelta(days=days)
        prev_since = since - timedelta(days=days)

        # --- Single query for current_rev, prev_rev, total_rev, total_count, success_count ---
        row = db.exec(
            select(
                func.coalesce(func.sum(case(
                    (Transaction.created_at >= since, Transaction.amount), else_=0
                )), 0),
                func.coalesce(func.sum(case(
                    (Transaction.created_at >= prev_since, case(
                        (Transaction.created_at < since, Transaction.amount), else_=0
                    )), else_=0
                )), 0),
                func.coalesce(func.sum(Transaction.amount), 0),
                func.count(Transaction.id),
            ).where(Transaction.status == TransactionStatus.SUCCESS)
        ).one()
        current_rev, prev_rev, total_rev, success_count = float(row[0]), float(row[1]), float(row[2]), int(row[3])

        total_tx = db.exec(select(func.count(Transaction.id))).one()
        growth = round(((current_rev - prev_rev) / prev_rev * 100) if prev_rev > 0 else 0, 1)

        # Revenue by type
        grouped = db.exec(
            select(Transaction.transaction_type, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= since)
            .group_by(Transaction.transaction_type)
        ).all()
        type_breakdown = [{"type": t.value if hasattr(t, "value") else str(t), "amount": round(a, 2)} for t, a in grouped if a > 0]

        # Monthly revenue chart (last 6 months) — use SQL group_by month
        start_6m = datetime.now(UTC).replace(day=1) - timedelta(days=30 * 5)
        monthly_rows = db.exec(
            select(
                func.date_trunc("month", Transaction.created_at),
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= start_6m)
            .group_by(func.date_trunc("month", Transaction.created_at))
            .order_by(func.date_trunc("month", Transaction.created_at))
        ).all()
        monthly_map = {r[0].strftime("%b"): round(float(r[1]), 2) for r in monthly_rows if r[0]}

        chart_data = []
        for i in range(5, -1, -1):
            m_start = datetime.now(UTC).replace(day=1) - timedelta(days=30 * i)
            label = m_start.strftime("%b")
            chart_data.append({"month": label, "value": monthly_map.get(label, 0)})

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
            "total_transactions": total_tx,
            "success_rate": round(success_count / max(total_tx, 1) * 100, 1),
        }

    return cached_call(_NS, "dashboard", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


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
    def _load():
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0)
        row = db.exec(
            select(
                func.count(Transaction.id),
                func.coalesce(func.sum(case((Transaction.status == TransactionStatus.SUCCESS, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Transaction.status == TransactionStatus.PENDING, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Transaction.status == TransactionStatus.FAILED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Transaction.status == TransactionStatus.SUCCESS, Transaction.amount), else_=0)), 0),
                func.coalesce(func.sum(case(
                    (Transaction.status == TransactionStatus.SUCCESS,
                     case((Transaction.created_at >= today_start, Transaction.amount), else_=0)),
                    else_=0
                )), 0),
            )
        ).one()
        return {
            "total_transactions": int(row[0]),
            "success_count": int(row[1]),
            "pending_count": int(row[2]),
            "failed_count": int(row[3]),
            "total_amount": round(float(row[4]), 2),
            "today_amount": round(float(row[5]), 2),
        }

    return cached_call("admin-finance", "transaction-stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


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
    dealer_map = {d.id: d for d in db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all()} if dealer_ids else {}

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
    def _load():
        row = db.exec(
            select(
                func.count(Settlement.id),
                func.coalesce(func.sum(case((Settlement.status == "pending", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Settlement.status == "paid", 1), else_=0)), 0),
                func.coalesce(func.sum(Settlement.net_payable), 0),
                func.coalesce(func.sum(case((Settlement.status == "paid", Settlement.net_payable), else_=0)), 0),
            )
        ).one()
        return {
            "total_settlements": int(row[0]),
            "pending_count": int(row[1]),
            "paid_count": int(row[2]),
            "total_payable": round(float(row[3]), 2),
            "total_paid": round(float(row[4]), 2),
        }

    return cached_call("admin-finance", "settlement-stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)

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
    def _load():
        row = db.exec(
            select(
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.total), 0),
                func.coalesce(func.sum(Invoice.tax_amount), 0),
            )
        ).one()
        return {
            "total_invoices": int(row[0]),
            "total_amount": round(float(row[1]), 2),
            "total_tax_collected": round(float(row[2]), 2),
        }

    return cached_call("admin-finance", "invoice-stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


# ─── PROFIT ANALYSIS ─────────────────────────────────────────────────────────

@router.get("/profit/analysis")
def get_profit_analysis(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Profit analysis with revenue, costs, and margins."""
    def _load():
        # --- Single query for revenue totals ---
        rev_row = db.exec(
            select(
                func.coalesce(func.sum(Transaction.amount), 0),
                func.coalesce(func.sum(Transaction.tax_amount), 0),
            ).where(Transaction.status == TransactionStatus.SUCCESS)
        ).one()
        total_revenue = float(rev_row[0])
        total_tax = float(rev_row[1])

        # --- Single query for settlement totals ---
        settle_row = db.exec(
            select(
                func.coalesce(func.sum(Settlement.total_commission), 0),
                func.coalesce(func.sum(Settlement.platform_fee), 0),
            )
        ).one()
        total_commissions = float(settle_row[0])
        total_platform_fees = float(settle_row[1])

        total_refunds = float(db.exec(select(func.coalesce(func.sum(Refund.amount), 0))).one())

        gross_profit = total_revenue - total_commissions - total_refunds
        net_profit = gross_profit - total_platform_fees
        margin = round((net_profit / total_revenue * 100) if total_revenue > 0 else 0, 1)

        # Monthly trend — SQL group_by month instead of loading all rows
        start_6m = datetime.now(UTC).replace(day=1) - timedelta(days=30 * 5)
        rev_monthly = db.exec(
            select(
                func.date_trunc("month", Transaction.created_at),
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= start_6m)
            .group_by(func.date_trunc("month", Transaction.created_at))
        ).all()
        rev_map = {r[0].strftime("%b %Y"): float(r[1]) for r in rev_monthly if r[0]}

        comm_monthly = db.exec(
            select(
                func.date_trunc("month", Settlement.created_at),
                func.coalesce(func.sum(Settlement.total_commission), 0),
            )
            .where(Settlement.created_at >= start_6m)
            .group_by(func.date_trunc("month", Settlement.created_at))
        ).all()
        comm_map = {r[0].strftime("%b %Y"): float(r[1]) for r in comm_monthly if r[0]}

        monthly_trend = []
        for i in range(5, -1, -1):
            m_start = datetime.now(UTC).replace(day=1) - timedelta(days=30 * i)
            label = m_start.strftime("%b %Y")
            m_rev = rev_map.get(label, 0)
            m_comm = comm_map.get(label, 0)
            monthly_trend.append({
                "month": label,
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

    return cached_call("admin-finance", "profit-analysis", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


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
