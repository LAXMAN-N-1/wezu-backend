"""
Financial Reporting Service — Revenue aggregation, reconciliation, and export.
"""

import csv
import io
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List

from sqlmodel import Session, select, func

from app.models.financial import Transaction, TransactionType
from app.models.revenue_report import RevenueReport

logger = logging.getLogger(__name__)


class FinancialReportService:

    # ─── Revenue Report Generation ───

    @staticmethod
    def generate_revenue_report(
        db: Session,
        period_type: str,  # daily, weekly, monthly
        target_date: date,
    ) -> RevenueReport:
        """
        Generate a revenue report for the given period.
        Aggregates transactions and persists the result.
        """
        period_start, period_end = FinancialReportService._resolve_period(period_type, target_date)

        # Core aggregation
        base = select(Transaction).where(
            Transaction.created_at >= datetime.combine(period_start, datetime.min.time()),
            Transaction.created_at < datetime.combine(period_end + timedelta(days=1), datetime.min.time()),
            Transaction.status == "success",
        )
        transactions = db.exec(base).all()

        total_revenue = sum(t.amount for t in transactions if t.amount > 0)
        total_refunds = sum(abs(t.amount) for t in transactions if t.transaction_type == TransactionType.REFUND)
        total_count = len(transactions)
        avg_value = (total_revenue / total_count) if total_count > 0 else 0.0
        net_revenue = total_revenue - total_refunds

        # Breakdown by category (using transaction_type as proxy for category)
        by_category: Dict[str, float] = {}
        for t in transactions:
            cat = t.transaction_type.value if hasattr(t.transaction_type, "value") else str(t.transaction_type)
            by_category[cat] = by_category.get(cat, 0.0) + abs(t.amount)

        # Breakdown by source
        by_source: Dict[str, float] = {}
        for t in transactions:
            type_str = str(t.transaction_type)
            source = "rental" if "RENTAL" in type_str or "SWAP" in type_str else "purchase"
            if "PURCHASE" not in type_str and "RENTAL" not in type_str and "SWAP" not in type_str:
                source = "other"
            by_source[source] = by_source.get(source, 0.0) + abs(t.amount)

        # Breakdown by station
        by_station: Dict[str, float] = {}
        for t in transactions:
            # If transaction has station_id (from rental/swap), group by it
            # Mocking station grouping for now as Transaction model doesn't have station_id directly
            # but usually it's derived from rental/swap.
            station = "Station-" + str(getattr(t, "station_id", "Unknown"))
            by_station[station] = by_station.get(station, 0.0) + abs(t.amount)

        # Growth vs previous period
        growth = FinancialReportService._calc_growth(db, period_type, period_start, total_revenue)

        report = RevenueReport(
            report_type=period_type,
            period_start=period_start,
            period_end=period_end,
            total_revenue=round(total_revenue, 2),
            total_transactions=total_count,
            avg_transaction_value=round(avg_value, 2),
            total_refunds=round(total_refunds, 2),
            net_revenue=round(net_revenue, 2),
            growth_percentage=round(growth, 2) if growth is not None else None,
            breakdown_by_category=by_category,
            breakdown_by_station=by_station,
            breakdown_by_source=by_source,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    # ─── Trends ───

    @staticmethod
    def get_trends(db: Session, period_type: str, num_periods: int = 6) -> List[dict]:
        """Return the last N generated reports as trend data."""
        reports = db.exec(
            select(RevenueReport)
            .where(RevenueReport.report_type == period_type)
            .order_by(RevenueReport.period_start.desc())
            .limit(num_periods)
        ).all()

        return [
            {
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "total_revenue": r.total_revenue,
                "total_transactions": r.total_transactions,
                "avg_transaction_value": r.avg_transaction_value,
                "net_revenue": r.net_revenue,
                "growth_percentage": r.growth_percentage,
            }
            for r in reversed(reports)  # oldest first for charting
        ]

    # ─── Reconciliation ───

    @staticmethod
    def get_reconciliation_report(db: Session, month: str) -> dict:
        """
        Compare internal transactions vs payment gateway transactions for a month.
        month format: '2026-02'
        """
        year, mon = map(int, month.split("-"))
        start = datetime(year, mon, 1)
        if mon == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, mon + 1, 1)

        # Internal totals
        internal_total = db.exec(
            select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(
                Transaction.created_at >= start,
                Transaction.created_at < end,
                Transaction.status == "success",
                Transaction.amount > 0,
            )
        ).one()

        internal_count = db.exec(
            select(func.count(Transaction.id)).where(
                Transaction.created_at >= start,
                Transaction.created_at < end,
                Transaction.status == "success",
                Transaction.amount > 0,
            )
        ).one()

        # Gateway totals (from razorpay_payment_id presence)
        gateway_total = db.exec(
            select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(
                Transaction.created_at >= start,
                Transaction.created_at < end,
                Transaction.status == "success",
                Transaction.razorpay_payment_id.isnot(None),
            )
        ).one()

        gateway_count = db.exec(
            select(func.count(Transaction.id)).where(
                Transaction.created_at >= start,
                Transaction.created_at < end,
                Transaction.status == "success",
                Transaction.razorpay_payment_id.isnot(None),
            )
        ).one()

        discrepancy = abs(float(internal_total) - float(gateway_total))

        return {
            "month": month,
            "internal_total": round(float(internal_total), 2),
            "internal_count": internal_count,
            "gateway_total": round(float(gateway_total), 2),
            "gateway_count": gateway_count,
            "discrepancy": round(discrepancy, 2),
            "reconciled": discrepancy < 1.0,
        }

    # ─── Export ───

    @staticmethod
    def export_report_csv(report: RevenueReport) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "report_type", "period_start", "period_end", "total_revenue",
            "total_transactions", "avg_transaction_value", "total_refunds",
            "net_revenue", "growth_percentage",
        ])
        writer.writerow([
            report.report_type, report.period_start.isoformat(), report.period_end.isoformat(),
            report.total_revenue, report.total_transactions, report.avg_transaction_value,
            report.total_refunds, report.net_revenue, report.growth_percentage or "",
        ])
        if report.breakdown_by_category:
            writer.writerow([])
            writer.writerow(["Category Breakdown"])
            writer.writerow(["category", "amount"])
            for cat, amt in report.breakdown_by_category.items():
                writer.writerow([cat, amt])
        return output.getvalue()

    @staticmethod
    def export_report_json(report: RevenueReport) -> dict:
        return {
            "id": report.id,
            "report_type": report.report_type,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_revenue": report.total_revenue,
            "total_transactions": report.total_transactions,
            "avg_transaction_value": report.avg_transaction_value,
            "total_refunds": report.total_refunds,
            "net_revenue": report.net_revenue,
            "growth_percentage": report.growth_percentage,
            "breakdown_by_category": report.breakdown_by_category,
            "breakdown_by_station": report.breakdown_by_station,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }

    @staticmethod
    def generate_revenue_forecast(db: Session, period_type: str) -> dict:
        """
        Generate a revenue forecast for the next period based on the last 3 periods.
        Uses a simple moving average and applies the recent growth trend.
        """
        reports = db.exec(
            select(RevenueReport)
            .where(RevenueReport.report_type == period_type)
            .order_by(RevenueReport.period_start.desc())
            .limit(3)
        ).all()

        if not reports:
            return {"forecasted_revenue": 0.0, "confidence": "low", "basis": "no historical data"}

        avg_revenue = sum(r.total_revenue for r in reports) / len(reports)
        
        # Calculate trend from the last two reports if available
        trend_factor = 1.0
        if len(reports) >= 2:
            latest = reports[0].total_revenue
            previous = reports[1].total_revenue
            if previous > 0:
                trend_factor = latest / previous

        forecast = avg_revenue * trend_factor

        return {
            "period_type": period_type,
            "forecasted_revenue": round(forecast, 2),
            "historical_average": round(avg_revenue, 2),
            "trend_factor": round(trend_factor, 2),
            "confidence": "medium" if len(reports) >= 3 else "low",
            "next_period_estimate": (datetime.now() + timedelta(days=30)).strftime("%Y-%m") if period_type == "monthly" else "next"
        }

    @staticmethod
    def get_revenue_comparison(db: Session, period_type: str, target_date: date) -> dict:
        """
        Detailed comparison: Current vs Previous vs Same-Period-Last-Year.
        """
        current_report = FinancialReportService.generate_revenue_report(db, period_type, target_date)
        
        # Previous Period
        if period_type == "daily":
            prev_date = target_date - timedelta(days=1)
            last_year_date = target_date - timedelta(days=365)
        elif period_type == "weekly":
            prev_date = target_date - timedelta(weeks=1)
            last_year_date = target_date - timedelta(weeks=52)
        else: # monthly
            if target_date.month == 1:
                prev_date = target_date.replace(year=target_date.year - 1, month=12)
            else:
                prev_date = target_date.replace(month=target_date.month - 1)
            last_year_date = target_date.replace(year=target_date.year - 1)

        prev_report = db.exec(
            select(RevenueReport).where(
                RevenueReport.report_type == period_type,
                RevenueReport.period_start == FinancialReportService._resolve_period(period_type, prev_date)[0]
            )
        ).first()

        last_year_report = db.exec(
            select(RevenueReport).where(
                RevenueReport.report_type == period_type,
                RevenueReport.period_start == FinancialReportService._resolve_period(period_type, last_year_date)[0]
            )
        ).first()

        def calc_change(curr: float, prev: Optional[RevenueReport]) -> float:
            if not prev or prev.total_revenue == 0:
                return 0.0
            return round(((curr - prev.total_revenue) / prev.total_revenue) * 100, 2)

        return {
            "period": period_type,
            "target_date": target_date.isoformat(),
            "current": {
                "revenue": current_report.total_revenue,
                "count": current_report.total_transactions
            },
            "previous_period": {
                "revenue": prev_report.total_revenue if prev_report else 0.0,
                "change_percent": calc_change(current_report.total_revenue, prev_report)
            },
            "last_year_period": {
                "revenue": last_year_report.total_revenue if last_year_report else 0.0,
                "change_percent": calc_change(current_report.total_revenue, last_year_report)
            }
        }

    # ─── Helpers ───

    @staticmethod
    def _resolve_period(period_type: str, target_date: date):
        if period_type == "daily":
            return target_date, target_date
        elif period_type == "weekly":
            start = target_date - timedelta(days=target_date.weekday())  # Monday
            end = start + timedelta(days=6)
            return start, end
        elif period_type == "monthly":
            start = target_date.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
            return start, end
        else:
            return target_date, target_date

    @staticmethod
    def _calc_growth(db: Session, period_type: str, current_start: date, current_revenue: float):
        """Calculate growth % vs previous period."""
        if period_type == "daily":
            prev_start = current_start - timedelta(days=1)
        elif period_type == "weekly":
            prev_start = current_start - timedelta(weeks=1)
        elif period_type == "monthly":
            if current_start.month == 1:
                prev_start = current_start.replace(year=current_start.year - 1, month=12)
            else:
                prev_start = current_start.replace(month=current_start.month - 1)
        else:
            return None

        prev = db.exec(
            select(RevenueReport)
            .where(
                RevenueReport.report_type == period_type,
                RevenueReport.period_start == prev_start,
            )
        ).first()

        if prev and prev.total_revenue > 0:
            return ((current_revenue - prev.total_revenue) / prev.total_revenue) * 100
        return None
