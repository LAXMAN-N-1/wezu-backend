"""
Admin Financial Reports API — Revenue reports, trends, reconciliation, and export.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.api.deps import get_current_active_superuser
from app.core.database import get_db
from app.models.revenue_report import RevenueReport
from app.models.user import User
from app.services.financial_report_service import FinancialReportService

router = APIRouter()


# ─── Schemas ───

class GenerateReportRequest(BaseModel):
    period_type: str = "daily"  # daily, weekly, monthly
    date: str  # ISO date, e.g. 2026-03-03


# ─── Endpoints ───

@router.get("/revenue")
def get_revenue_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    period: str = Query("daily", description="daily, weekly, or monthly"),
    target_date: str = Query(None, alias="date", description="ISO date (e.g. 2026-03-03)"),
):
    """
    Get or generate a revenue report for the given period.
    If a report already exists for this period, returns it; otherwise generates one.
    """
    dt = _parse_date(target_date)
    period_start, _ = FinancialReportService._resolve_period(period, dt)

    # Check for existing
    existing = db.exec(
        select(RevenueReport).where(
            RevenueReport.report_type == period,
            RevenueReport.period_start == period_start,
        )
    ).first()

    if existing:
        return FinancialReportService.export_report_json(existing)

    report = FinancialReportService.generate_revenue_report(db, period, dt)
    return FinancialReportService.export_report_json(report)


@router.get("/revenue/trends")
def get_revenue_trends(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    period_type: str = Query("monthly"),
    periods: int = Query(6, ge=1, le=24),
):
    """Get revenue trends for the last N periods."""
    return FinancialReportService.get_trends(db, period_type, periods)


@router.get("/reconciliation")
def get_reconciliation_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    month: str = Query(..., description="Month in YYYY-MM format"),
):
    """Get reconciliation report comparing internal vs gateway totals."""
    try:
        year, mon = map(int, month.split("-"))
        if not (1 <= mon <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")

    return FinancialReportService.get_reconciliation_report(db, month)


@router.post("/generate")
def generate_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: GenerateReportRequest,
):
    """Trigger on-demand report generation for a specific period."""
    if request.period_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period_type must be daily, weekly, or monthly")

    dt = _parse_date(request.date)
    report = FinancialReportService.generate_revenue_report(db, request.period_type, dt)
    return FinancialReportService.export_report_json(report)


@router.get("/export/csv")
def export_report_csv(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    report_id: int = Query(...),
):
    """Download a report as CSV."""
    report = db.get(RevenueReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    csv_content = FinancialReportService.export_report_csv(report)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.csv"},
    )


@router.get("/export/json")
def export_report_json(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    report_id: int = Query(...),
):
    """Download a report as JSON."""
    report = db.get(RevenueReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    data = FinancialReportService.export_report_json(report)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.json"},
    )


@router.get("/history")
def list_reports(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    report_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List generated reports with optional type filter and pagination."""
    query = select(RevenueReport)
    if report_type:
        query = query.where(RevenueReport.report_type == report_type)

    total = db.exec(select(func.count()).select_from(query.subquery())).one()
    reports = db.exec(
        query.order_by(RevenueReport.period_start.desc()).offset(skip).limit(limit)
    ).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [FinancialReportService.export_report_json(r) for r in reports],
    }


@router.get("/{report_id}")
def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Get a specific report by ID."""
    report = db.get(RevenueReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return FinancialReportService.export_report_json(report)


# ─── Helpers ───

def _parse_date(date_str: Optional[str]) -> date:
    if not date_str:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD.")
