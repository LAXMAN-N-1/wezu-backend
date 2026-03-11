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

from app.models.financial import Transaction
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

        total_revenue = sum(t.amount for t in transactions if t.type == "credit")
        total_refunds = sum(abs(t.amount) for t in transactions if t.category == "refund")
        total_count = len(transactions)
        avg_value = (total_revenue / total_count) if total_count > 0 else 0.0
        net_revenue = total_revenue - total_refunds

        # Breakdown by category
        by_category: Dict[str, float] = {}
        for t in transactions:
            cat = t.category or "other"
            by_category[cat] = by_category.get(cat, 0.0) + abs(t.amount)

        # Breakdown by reference_type (proxy for payment method / source)
        by_station: Dict[str, float] = {}
        for t in transactions:
            ref = t.reference_type or "direct"
            by_station[ref] = by_station.get(ref, 0.0) + abs(t.amount)

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
                Transaction.type == "credit",
            )
        ).one()

        internal_count = db.exec(
            select(func.count(Transaction.id)).where(
                Transaction.created_at >= start,
                Transaction.created_at < end,
                Transaction.status == "success",
                Transaction.type == "credit",
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
