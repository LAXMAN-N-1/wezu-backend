"""
Dealer Analytics API — Performance overview, trends, station metrics,
customer insights, peak hours, and export.
All endpoints require dealer role.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.services.dealer_analytics_service import DealerAnalyticsService

router = APIRouter()


def _get_dealer_id(db: Session, user_id: int) -> int:
    """Resolve dealer_id from current user, or raise 403."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    return dealer.id


@router.get("/overview")
def get_overview(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Performance overview: swap counts (today/month), revenue,
    avg rating, active batteries, station count.
    """
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_overview(db, dealer_id)


@router.get("/trends")
def get_trends(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    period: str = Query("daily", description="daily, weekly, or monthly"),
    periods: int = Query(7, ge=1, le=30),
) -> Any:
    """Revenue + swap volume trends for the last N periods."""
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period must be daily, weekly, or monthly")
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_trends(db, dealer_id, period, periods)


@router.get("/stations")
def get_station_metrics(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Per-station: swaps, revenue, utilization %, rating."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_station_metrics(db, dealer_id)

@router.get("/comparison")
def get_comparison(
    period: str = Query("daily", description="daily, weekly, or monthly"),
    periods: int = Query(7, ge=2, le=30),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Compare current vs previous period trends."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_comparison_trends(db, dealer_id, period, periods)

@router.get("/revenue-breakdown")
def get_revenue_breakdown(
    period: str = "month",
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Breakdown of revenue for Stacked Bar Charts."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_revenue_breakdown(db, dealer_id, period)


@router.get("/customers")
def get_customer_insights(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer insights: repeat %, new acquisition, CLV, churn rate."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_customer_insights(db, dealer_id)


@router.get("/peak-hours")
def get_peak_hours(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Hourly swap distribution (last 30 days)."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_peak_hours(db, dealer_id)


@router.get("/profitability")
def get_profitability_analysis(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get detailed profitability analysis (Revenue vs Estimated Costs)."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_profitability_analysis(db, dealer_id)


@router.get("/margin-by-battery")
def get_margin_by_battery(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get revenue/cost breakdown by battery type."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.get_margin_by_battery_type(db, dealer_id)


@router.get("/export/csv")
def export_csv(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Download performance overview as CSV."""
    dealer_id = _get_dealer_id(db, current_user.id)
    data = DealerAnalyticsService.get_overview(db, dealer_id)
    csv_content = DealerAnalyticsService.export_csv(data)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dealer_performance.csv"},
    )


@router.get("/export/json")
def export_json(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Download performance overview as JSON."""
    dealer_id = _get_dealer_id(db, current_user.id)
    data = DealerAnalyticsService.get_overview(db, dealer_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": "attachment; filename=dealer_performance.json"},
    )


@router.get("/export/pdf")
def export_pdf(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Download performance overview as PDF."""
    from fastapi.responses import FileResponse
    dealer_id = _get_dealer_id(db, current_user.id)
    data = DealerAnalyticsService.get_overview(db, dealer_id)
    pdf_path = DealerAnalyticsService.export_pdf(data)
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="dealer_performance.pdf"
    )


@router.post("/email-report")
def email_report(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Email the performance report to the dealer."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerAnalyticsService.email_report(db, dealer_id)

@router.get("/commission-summary")
def get_commission_summary(
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Aggregates Commission and Settlements for the Settlement Command Center."""
    from app.models.settlement import Settlement
    from app.models.commission import CommissionLog
    from sqlalchemy import func
    from datetime import datetime
    
    dealer_id = _get_dealer_id(db, current_user.id)
    
    settlement_q = select(Settlement).where(Settlement.dealer_id == dealer_id)
    
    if from_date:
        try:
            fd = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            settlement_q = settlement_q.where(Settlement.created_at >= fd)
        except: pass
    if to_date:
        try:
            td = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            settlement_q = settlement_q.where(Settlement.created_at <= td)
        except: pass
        
    settlements = db.exec(settlement_q).all()
    
    gross_revenue = sum(s.total_revenue for s in settlements)
    platform_fees = sum(s.platform_fee for s in settlements)
    net_payout = sum(s.net_payable for s in settlements)
    commission_earned = sum(s.total_commission for s in settlements)
    
    # Determine commission rate from config if possible
    from app.models.commission import CommissionConfig
    config = db.exec(
        select(CommissionConfig)
        .where(CommissionConfig.dealer_id == current_user.id)
        .order_by(CommissionConfig.created_at.desc())
    ).first()
    
    current_rate = config.percentage if config else 15.0
    
    return {
        "gross_revenue": gross_revenue,
        "platform_fees_deducted": platform_fees,
        "commission_earned": commission_earned,
        "net_payout": net_payout,
        "current_commission_rate": current_rate
    }
