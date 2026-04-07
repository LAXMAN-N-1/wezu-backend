"""
Dealer Analytics Service — Performance overview, trends, station metrics,
customer insights, peak hours, and export.
"""

import csv
import io
import logging
from datetime import datetime, UTC, timedelta, date
from typing import Dict, Any, List, Optional

from sqlmodel import Session, select, func, col

from app.models.swap import SwapSession
from app.models.station import Station, StationSlot
from app.models.commission import CommissionLog

logger = logging.getLogger(__name__)


class DealerAnalyticsService:

    # ─── 1. Performance Overview ───

    @staticmethod
    def get_overview(
        db: Session, 
        dealer_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        station_id: Optional[int] = None
    ) -> dict:
        """
        Returns: swap counts, revenue, avg rating,
        active batteries, and station count within a range.
        """
        now = datetime.now(UTC)
        
        # Default to current month if no range provided
        if not start_date:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = now

        # Dealer's station IDs
        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id, station_id=station_id)

        # Swap counts and Revenue
        swaps_count = 0
        revenue = 0.0
        if station_ids:
            swaps_count = db.exec(
                select(func.count(SwapSession.id)).where(
                    col(SwapSession.station_id).in_(station_ids),
                    SwapSession.status == "completed",
                    SwapSession.created_at >= start_date,
                    SwapSession.created_at <= end_date,
                )
            ).one() or 0

            revenue = db.exec(
                select(func.coalesce(func.sum(SwapSession.swap_amount), 0.0)).where(
                    col(SwapSession.station_id).in_(station_ids),
                    SwapSession.status == "completed",
                    SwapSession.created_at >= start_date,
                    SwapSession.created_at <= end_date,
                )
            ).one() or 0.0

            # Delta calculation based on previous equivalent period
            period_delta = end_date - start_date
            prev_start = start_date - period_delta
            prev_end = start_date

            revenue_prev = db.exec(
                select(func.coalesce(func.sum(SwapSession.swap_amount), 0.0)).where(
                    col(SwapSession.station_id).in_(station_ids),
                    SwapSession.status == "completed",
                    SwapSession.created_at >= prev_start,
                    SwapSession.created_at < prev_end,
                )
            ).one() or 0.0
        else:
            revenue_prev = 0.0

        # Average station rating
        rating_query = select(func.coalesce(func.avg(Station.rating), 0.0)).where(
            Station.dealer_id == dealer_id,
        )
        if station_id:
            rating_query = rating_query.where(Station.id == station_id)
        
        avg_rating = db.exec(rating_query).one() or 0.0

        # Customer rating distribution
        rating_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        if station_ids:
            from app.models.review import Review
            ratings = db.exec(
                select(Review.rating, func.count()).where(
                    col(Review.station_id).in_(station_ids),
                    Review.rating.isnot(None),
                    Review.created_at >= start_date,
                    Review.created_at <= end_date,
                ).group_by(Review.rating)
            ).all()
            for r_val, count in ratings:
                str_val = str(int(r_val))
                if str_val in rating_dist:
                    rating_dist[str_val] = count

        # Active batteries in slots
        active_batteries = 0
        if station_ids:
            active_batteries = db.exec(
                select(func.count(StationSlot.id)).where(
                    col(StationSlot.station_id).in_(station_ids),
                    StationSlot.battery_id.isnot(None),
                )
            ).one() or 0

        # Station count
        station_count = len(station_ids) if not station_id else 1

        return {
            "swaps_count": swaps_count,
            "revenue": round(float(revenue), 2),
            "revenue_prev": round(float(revenue_prev), 2),
            "revenue_delta_pct": round(((revenue - revenue_prev) / revenue_prev * 100), 1) if revenue_prev > 0 else 0.0,
            "avg_rating": round(float(avg_rating), 2),
            "rating_distribution": rating_dist,
            "active_batteries": active_batteries,
            "station_count": station_count,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timestamp": now.isoformat(),
        }

    @staticmethod
    def get_sales_kpis(db: Session, dealer_id: int) -> dict:
        """
        Calculates 4 specific KPI cards for the Sales & Revenue screen:
        1. Today's Revenue (vs Yesterday)
        2. Weekly Revenue (vs Last Week)
        3. Monthly Revenue (vs Last Month)
        4. Pending Settlement (Amount + due date)
        """
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        
        week_start = (today_start - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_start = week_start - timedelta(weeks=1)
        
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id)

        def _get_revenue(start, end):
            if not station_ids: return 0.0
            return db.exec(
                select(func.coalesce(func.sum(SwapSession.swap_amount), 0.0)).where(
                    col(SwapSession.station_id).in_(station_ids),
                    SwapSession.status == "completed",
                    SwapSession.created_at >= start,
                    SwapSession.created_at < end,
                )
            ).one() or 0.0

        def _get_count(start, end):
            if not station_ids: return 0
            return db.exec(
                select(func.count(SwapSession.id)).where(
                    col(SwapSession.station_id).in_(station_ids),
                    SwapSession.status == "completed",
                    SwapSession.created_at >= start,
                    SwapSession.created_at < end,
                )
            ).one() or 0

        # Calculations
        rev_today = _get_revenue(today_start, now)
        rev_yesterday = _get_revenue(yesterday_start, today_start)
        count_today = _get_count(today_start, now)
        avg_txn_today = (rev_today / count_today) if count_today > 0 else 0.0

        rev_week = _get_revenue(week_start, now)
        rev_last_week = _get_revenue(last_week_start, week_start)
        count_week = _get_count(week_start, now)

        rev_month = _get_revenue(month_start, now)
        rev_last_month = _get_revenue(last_month_start, month_start)

        # Pending Settlement from SettlementService
        from app.services.settlement_service import SettlementService
        settlement_info = SettlementService.get_dealer_dashboard(db, dealer_id)
        pending_amount = settlement_info["pending_settlements"]["total_amount"]
        
        # Estimate due date (standard 10th of next month)
        next_due = (now.replace(day=28) + timedelta(days=5)).replace(day=10, hour=0, minute=0)

        return {
            "today": {
                "value": round(float(rev_today), 2),
                "prev_value": round(float(rev_yesterday), 2),
                "delta_pct": round(((rev_today - rev_yesterday) / rev_yesterday * 100), 1) if rev_yesterday > 0 else 0.0,
                "count": count_today,
                "avg_value": round(float(avg_txn_today), 2)
            },
            "week": {
                "value": round(float(rev_week), 2),
                "prev_value": round(float(rev_last_week), 2),
                "delta_pct": round(((rev_week - rev_last_week) / rev_last_week * 100), 1) if rev_last_week > 0 else 0.0,
                "count": count_week
            },
            "month": {
                "value": round(float(rev_month), 2),
                "prev_value": round(float(rev_last_month), 2),
                "delta_pct": round(((rev_month - rev_last_month) / rev_last_month * 100), 1) if rev_last_month > 0 else 0.0,
                "target": 50000.0 # Mock target
            },
            "pending": {
                "value": round(float(pending_amount), 2),
                "due_date": next_due.isoformat()
            }
        }

    @staticmethod
    def get_revenue_breakdown(
        db: Session, 
        dealer_id: int, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        station_id: Optional[int] = None
    ) -> dict:
        """Returns revenue split by type (Rentals, Commissions, Refunds) for Stacked Bar Charts."""
        now = datetime.now(UTC)
        if not start_date:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = now

        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id, station_id=station_id)
        
        rental_income = 0.0
        if station_ids:
            from app.models.rental import Rental
            rental_income = db.exec(
                select(func.coalesce(func.sum(Rental.total_amount), 0.0))
                .where(col(Rental.start_station_id).in_(station_ids))
                .where(Rental.created_at >= start_date)
                .where(Rental.created_at <= end_date)
            ).one() or 0.0
            
        commission = db.exec(
            select(func.coalesce(func.sum(CommissionLog.amount), 0.0))
            .where(CommissionLog.dealer_id == dealer_id)
            .where(CommissionLog.created_at >= start_date)
            .where(CommissionLog.created_at <= end_date)
        ).one() or 0.0
        
        return {
            "rental_income": round(float(rental_income), 2),
            "commission": round(float(commission), 2),
            "refunds": 0.0,
            "bonuses": 0.0
        }

    # ─── 2. Trends ───

    @staticmethod
    def get_trends(
        db: Session, 
        dealer_id: int, 
        period: str = "daily", 
        num_periods: int = 7,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        station_id: Optional[int] = None
    ) -> List[dict]:
        """Revenue + swap volume trends for specific range or N periods."""
        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id, station_id=station_id)
        if not station_ids:
            return []

        now = end_date or datetime.now(UTC)
        trends = []

        # If start_date is provided, we calculate based on the range.
        # Otherwise, we use num_periods as before.
        if start_date:
            # Simple logic: If daily, we iterate days. If monthly, we iterate months.
            current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            while current < now:
                if period == "daily":
                    next_p = current + timedelta(days=1)
                    label = current.strftime("%Y-%m-%d")
                elif period == "weekly":
                    next_p = current + timedelta(weeks=1)
                    label = f"W{current.isocalendar().week} {current.year}"
                else: # monthly
                    if current.month == 12:
                        next_p = datetime(current.year + 1, 1, 1)
                    else:
                        next_p = datetime(current.year, current.month + 1, 1)
                    label = current.strftime("%Y-%m")
                
                swaps = db.exec(
                    select(func.count(SwapSession.id)).where(
                        col(SwapSession.station_id).in_(station_ids),
                        SwapSession.status == "completed",
                        SwapSession.created_at >= current,
                        SwapSession.created_at < next_p,
                    )
                ).one() or 0

                revenue = db.exec(
                    select(func.coalesce(func.sum(SwapSession.swap_amount), 0.0)).where(
                        col(SwapSession.station_id).in_(station_ids),
                        SwapSession.status == "completed",
                        SwapSession.created_at >= current,
                        SwapSession.created_at < next_p,
                    )
                ).one() or 0.0

                trends.append({
                    "period": label,
                    "swaps": swaps,
                    "revenue": round(float(revenue), 2),
                })
                current = next_p
        else:
            # Original logic for last N periods
            for i in range(num_periods - 1, -1, -1):  # oldest first
                if period == "daily":
                    start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
                    end = start + timedelta(days=1)
                    label = start.strftime("%Y-%m-%d")
                elif period == "weekly":
                    start = (now - timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
                    start = start - timedelta(days=start.weekday())  # Monday
                    end = start + timedelta(weeks=1)
                    label = f"W{start.isocalendar().week} {start.year}"
                else:  # monthly
                    month_offset = now.month - i
                    year = now.year
                    while month_offset < 1:
                        month_offset += 12
                        year -= 1
                    start = datetime(year, month_offset, 1)
                    if month_offset == 12:
                        end = datetime(year + 1, 1, 1)
                    else:
                        end = datetime(year, month_offset + 1, 1)
                    label = start.strftime("%Y-%m")

                swaps = db.exec(
                    select(func.count(SwapSession.id)).where(
                        col(SwapSession.station_id).in_(station_ids),
                        SwapSession.status == "completed",
                        SwapSession.created_at >= start,
                        SwapSession.created_at < end,
                    )
                ).one() or 0

                revenue = db.exec(
                    select(func.coalesce(func.sum(SwapSession.swap_amount), 0.0)).where(
                        col(SwapSession.station_id).in_(station_ids),
                        SwapSession.status == "completed",
                        SwapSession.created_at >= start,
                        SwapSession.created_at < end,
                    )
                ).one() or 0.0

                trends.append({
                    "period": label,
                    "swaps": swaps,
                    "revenue": round(float(revenue), 2),
                })

        return trends

    @staticmethod
    def get_comparison_trends(
        db: Session, dealer_id: int, period: str = "daily", num_periods: int = 7
    ) -> List[dict]:
        """Revenue + swap volume trends for current period vs previous period."""
        current_trends = DealerAnalyticsService.get_trends(db, dealer_id, period, num_periods)
        
        now = datetime.now(UTC)
        if period == "daily":
            prev_end = now - timedelta(days=num_periods)
        elif period == "weekly":
            prev_end = now - timedelta(weeks=num_periods)
        else:
            month_offset = now.month - num_periods
            year = now.year
            while month_offset < 1:
                month_offset += 12
                year -= 1
            # Just approximation for rolling month shift
            prev_end = datetime(year, month_offset, now.day if now.day <= 28 else 28)
            
        prev_trends = DealerAnalyticsService.get_trends(db, dealer_id, period, num_periods, end_date=prev_end)
        
        comparison = []
        for i in range(len(current_trends)):
            curr = current_trends[i]
            prev = prev_trends[i] if i < len(prev_trends) else {"swaps": 0, "revenue": 0.0}
            comparison.append({
                "period": curr["period"],
                "swaps": curr["swaps"],
                "revenue": curr["revenue"],
                "prev_swaps": prev["swaps"],
                "prev_revenue": prev["prev_revenue"] if "prev_revenue" in prev else prev["revenue"]
            })
        return comparison

    # ─── 3. Station Metrics ───

    @staticmethod
    def get_station_metrics(
        db: Session, 
        dealer_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[dict]:
        """Per-station performance within a range."""
        stations = db.exec(
            select(Station).where(Station.dealer_id == dealer_id)
        ).all()

        now = datetime.now(UTC)
        if not start_date:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = now

        metrics = []

        for s in stations:
            swaps = db.exec(
                select(func.count(SwapSession.id)).where(
                    SwapSession.station_id == s.id,
                    SwapSession.status == "completed",
                    SwapSession.created_at >= start_date,
                    SwapSession.created_at <= end_date,
                )
            ).one() or 0

            revenue = db.exec(
                select(func.coalesce(func.sum(SwapSession.swap_amount), 0.0)).where(
                    SwapSession.station_id == s.id,
                    SwapSession.status == "completed",
                    SwapSession.created_at >= start_date,
                    SwapSession.created_at <= end_date,
                )
            ).one() or 0.0

            # Utilization: slots with batteries / total slots
            occupied = db.exec(
                select(func.count(StationSlot.id)).where(
                    StationSlot.station_id == s.id,
                    StationSlot.battery_id.isnot(None),
                )
            ).one() or 0

            utilization = (occupied / s.total_slots * 100) if s.total_slots > 0 else 0.0

            # Battery Health Score (average health of batteries present)
            from app.models.battery import Battery
            avg_health = db.exec(
                select(func.coalesce(func.avg(Battery.health_percentage), 0.0)).join(
                    StationSlot, StationSlot.battery_id == Battery.id
                ).where(
                    StationSlot.station_id == s.id
                )
            ).one() or 0.0

            metrics.append({
                "station_id": s.id,
                "station_name": s.name,
                "swaps_month": swaps,
                "revenue_month": round(float(revenue), 2),
                "utilization_pct": round(utilization, 1),
                "health_score_pct": round(float(avg_health), 1),
                "rating": s.rating,
                "total_slots": s.total_slots,
                "status": s.status,
            })

        return metrics

    # ─── 4. Customer Insights ───

    @staticmethod
    def get_customer_insights(db: Session, dealer_id: int) -> dict:
        """Repeat %, new customers, avg CLV, churn rate estimate."""
        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id)
        if not station_ids:
            return {
                "total_unique_customers": 0,
                "repeat_customer_pct": 0.0,
                "new_customers_month": 0,
                "avg_customer_lifetime_value": 0.0,
                "churn_rate_pct": 0.0,
            }

        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

        # All unique customers
        all_customers = db.exec(
            select(SwapSession.user_id).where(
                col(SwapSession.station_id).in_(station_ids),
                SwapSession.status == "completed",
            ).distinct()
        ).all()
        total = len(all_customers)

        # Repeat: customers with > 1 swap
        from sqlalchemy import literal_column
        repeat_subq = (
            select(SwapSession.user_id).where(
                col(SwapSession.station_id).in_(station_ids),
                SwapSession.status == "completed",
            )
            .group_by(SwapSession.user_id)
            .having(func.count(SwapSession.id) > 1)
        )
        repeat_users = db.exec(select(func.count()).select_from(repeat_subq.subquery())).one() or 0
        repeat_pct = (repeat_users / total * 100) if total > 0 else 0.0

        # New this month
        prev_customers = set(db.exec(
            select(SwapSession.user_id).where(
                col(SwapSession.station_id).in_(station_ids),
                SwapSession.status == "completed",
                SwapSession.created_at < month_start,
            ).distinct()
        ).all())

        current_customers = set(db.exec(
            select(SwapSession.user_id).where(
                col(SwapSession.station_id).in_(station_ids),
                SwapSession.status == "completed",
                SwapSession.created_at >= month_start,
            ).distinct()
        ).all())

        new_customers = len(current_customers - prev_customers)

        # Avg CLV (total revenue / unique customers)
        total_revenue = db.exec(
            select(func.coalesce(func.sum(SwapSession.amount), 0.0)).where(
                col(SwapSession.station_id).in_(station_ids),
                SwapSession.status == "completed",
            )
        ).one() or 0.0
        avg_clv = (float(total_revenue) / total) if total > 0 else 0.0

        # Churn estimate: customers active last month but not this month
        churned = len(prev_customers - current_customers) if current_customers else 0
        prev_total = len(prev_customers) if prev_customers else 1
        churn_rate = (churned / prev_total * 100) if prev_total > 0 else 0.0

        # NPS Calculation: % Promoters (4-5) - % Detractors (1-2)
        from app.models.review import Review
        total_ratings = db.exec(
            select(func.count(Review.id)).where(
                col(Review.station_id).in_(station_ids),
                Review.rating.isnot(None),
            )
        ).one() or 0

        nps_score = 0.0
        if total_ratings > 0:
            promoters = db.exec(
                select(func.count(Review.id)).where(
                    col(Review.station_id).in_(station_ids),
                    Review.rating >= 4,
                )
            ).one() or 0
            
            detractors = db.exec(
                select(func.count(Review.id)).where(
                    col(Review.station_id).in_(station_ids),
                    Review.rating <= 2,
                )
            ).one() or 0
            
            promoter_pct = (promoters / total_ratings) * 100
            detractor_pct = (detractors / total_ratings) * 100
            nps_score = promoter_pct - detractor_pct

        return {
            "total_unique_customers": total,
            "repeat_customer_pct": round(repeat_pct, 1),
            "new_customers_month": new_customers,
            "avg_customer_lifetime_value": round(avg_clv, 2),
            "churn_rate_pct": round(churn_rate, 1),
            "nps_score": round(nps_score, 1),
        }

    # ─── 5. Peak Hours ───

    @staticmethod
    def get_peak_hours(db: Session, dealer_id: int) -> List[dict]:
        """Hourly swap distribution (0-23) for the last 30 days."""
        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id)
        if not station_ids:
            return [{"hour": h, "swap_count": 0} for h in range(24)]

        since = datetime.now(UTC) - timedelta(days=30)
        # Get all completed swaps in the last 30 days
        swaps = db.exec(
            select(SwapSession).where(
                col(SwapSession.station_id).in_(station_ids),
                SwapSession.status == "completed",
                SwapSession.created_at >= since,
            )
        ).all()

        hourly = {h: 0 for h in range(24)}
        for swap in swaps:
            hourly[swap.created_at.hour] += 1

        return [{"hour": h, "swap_count": c} for h, c in sorted(hourly.items())]

    # ─── 6. Export ───

    @staticmethod
    def export_csv(data: dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for key, val in data.items():
            if isinstance(val, (dict, list)):
                writer.writerow([key, str(val)])
            else:
                writer.writerow([key, val])
        return output.getvalue()

    @staticmethod
    def export_pdf(data: dict) -> str:
        """Generate PDF using PDFService."""
        from app.services.pdf_service import PDFService
        from datetime import datetime, UTC
        import uuid
        import os

        # Use an invoice/report generator logic
        filename = f"dealer_report_{data.get('station_count', 0)}_{uuid.uuid4().hex[:6]}.pdf"
        filepath = f"/tmp/{filename}"

        # Assuming PDFService has generate_invoice that writes to a file
        # We'll build the data dict for PDFService
        pdf_data = {
            "invoice_number": f"REP-{datetime.now(UTC).strftime('%Y%M')}",
            "dealer_report": True,
            "date": data.get("timestamp"),
            "amount_due": data.get("revenue_month"),
        }
        for k, v in data.items():
            pdf_data[k] = v

        try:
            # We don't have a direct raw PDF generator, so we use this mock
            # Or build a simple FPDF right here
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=15)
            pdf.cell(200, 10, txt="Dealer Performance Report", ln=1, align="C")
            pdf.set_font("Arial", size=10)
            for k, v in data.items():
                if isinstance(v, dict):
                    pdf.cell(200, 10, txt=f"{k}:", ln=1, align="L")
                    for k2, v2 in v.items():
                        pdf.cell(200, 10, txt=f"    {k2}: {v2}", ln=1, align="L")
                else:
                    pdf.cell(200, 10, txt=f"{k}: {v}", ln=1, align="L")
            pdf.output(filepath)
            return filepath
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise e

    @staticmethod
    def email_report(db: Session, dealer_id: int):
        """Generates report and emails it to dealer."""
        from app.models.dealer import DealerProfile
        from app.services.email_service import EmailService

        dealer = db.exec(select(DealerProfile).where(DealerProfile.id == dealer_id)).first()
        if not dealer or not dealer.contact_email:
            raise Exception("Dealer email not found.")

        # Get data and generate PDF
        data = DealerAnalyticsService.get_overview(db, dealer_id)
        
        # We append a customer insight block to it
        cust_data = DealerAnalyticsService.get_customer_insights(db, dealer_id)
        data.update(cust_data)

        pdf_path = DealerAnalyticsService.export_pdf(data)

        # Send email
        body = f"Attached is your performance overview up to {datetime.now(UTC).isoformat()}."
        # In actual prod we attach the file via EmailService (which is currently mocked)
        EmailService.send_email(dealer.contact_email, "Dealer Performance Report", body)
        return {"status": "success", "email": dealer.contact_email}

    # ─── Helpers ───

    @staticmethod
    def get_profitability_analysis(db: Session, dealer_id: int) -> dict:
        """
        Comprehensive profitability analysis for the dealer.
        Formula: Revenue - (Depreciation + Estimated Power Cost + Maintenance)
        """
        overview = DealerAnalyticsService.get_overview(db, dealer_id)
        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id)
        
        revenue = overview["revenue_month"]
        
        # Estimate costs
        from app.models.battery import Battery
        total_asset_value = db.exec(
            select(func.sum(Battery.purchase_cost)).where(
                col(Battery.station_id).in_(station_ids)
            )
        ).one() or 0.0
        monthly_depreciation = total_asset_value * 0.01
        
        swaps = overview["swaps_month"]
        power_cost = swaps * 10.0
        maintenance_cost = len(station_ids) * 500.0
        
        total_cost = monthly_depreciation + power_cost + maintenance_cost
        gross_profit = revenue - total_cost
        margin_pct = (gross_profit / revenue * 100) if revenue > 0 else 0.0
        
        return {
            "revenue": revenue,
            "estimated_costs": {
                "depreciation": round(float(monthly_depreciation), 2),
                "power": round(power_cost, 2),
                "maintenance": round(maintenance_cost, 2),
                "total": round(float(total_cost), 2)
            },
            "gross_profit": round(float(gross_profit), 2),
            "margin_percentage": round(margin_pct, 1),
            "forecast_next_month_profit": round(float(gross_profit * 1.05), 2)
        }

    @staticmethod
    def get_margin_by_battery_type(db: Session, dealer_id: int) -> List[dict]:
        """Breakdown of revenue vs estimated cost per battery type."""
        from app.models.battery import Battery
        station_ids = DealerAnalyticsService._get_station_ids(db, dealer_id)
        if not station_ids:
            return []
            
        battery_data = db.exec(
            select(Battery.battery_type, func.count(Battery.id), func.sum(Battery.purchase_cost))
            .where(col(Battery.station_id).in_(station_ids))
            .group_by(Battery.battery_type)
        ).all()
        
        results = []
        for b_type, count, cost in battery_data:
            results.append({
                "battery_type": b_type,
                "count": count,
                "asset_value": round(float(cost), 2),
                "monthly_depreciation": round(float(cost) * 0.01, 2)
            })
            
        return results

    # ─── Helpers ───
    @staticmethod
    def _get_station_ids(db: Session, dealer_id: int, station_id: Optional[int] = None) -> List[int]:
        query = select(Station.id).where(Station.dealer_id == dealer_id)
        if station_id:
            query = query.where(Station.id == station_id)
        return list(db.exec(query).all())
