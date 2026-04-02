from sqlmodel import Session, select, func, and_
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
from sqlalchemy import case
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.rental import Rental, RentalStatus
from app.models.station import Station, StationSlot
from app.models.battery import Battery

class AnalyticsService:
    @staticmethod
    def _period_to_range(period: str):
        """Return (start, end, prev_start, prev_end, days) for a given period string."""
        normalized = (period or "").lower()
        if normalized in ["today", "1d", "24h", "daily"]:
            days = 1
        elif normalized in ["7d", "week", "weekly"]:
            days = 7
        elif normalized in ["90d", "quarter"]:
            days = 90
        else:
            # default 30d
            days = 30

        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        prev_end = start
        prev_start = start - timedelta(days=days)
        return start, end, prev_start, prev_end, days

    @staticmethod
    def get_revenue_stats(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate revenue by type and count transactions for a period"""
        # Base query for success transactions in range
        base_stmt = select(Transaction).where(
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.created_at >= start_date,
            Transaction.created_at <= end_date
        )
        transactions = db.exec(base_stmt).all()
        
        total_rev = sum(t.amount for t in transactions)
        rental_rev = sum(t.amount for t in transactions if t.transaction_type == TransactionType.RENTAL_PAYMENT)
        purchase_rev = sum(t.amount for t in transactions if t.transaction_type == TransactionType.PURCHASE)
        
        # Simple comparison logic (mocking previous period for now or querying if needed)
        # For production, we would query the preceding period of same duration
        
        return {
            "period": f"{start_date.date()} to {end_date.date()}",
            "total_revenue": round(total_rev, 2),
            "rental_revenue": round(rental_rev, 2),
            "purchase_revenue": round(purchase_rev, 2),
            "transaction_count": len(transactions),
            "comparison_percentage": 5.2 # Mocked growth
        }

    @staticmethod
    def get_revenue_by_station(db: Session) -> List[Dict[str, Any]]:
        """Revenue breakdown per station"""
        # Join Rental with Transaction to get revenue per station
        # Note: Some transactions might not be linked to rentals (topups/purchases)
        results = []
        stations = db.exec(select(Station)).all()
        
        for station in stations:
            # Sum rental payments linked to this station
            stmt = select(func.sum(Transaction.amount)).join(Rental).where(
                Rental.start_station_id == station.id,
                Transaction.status == TransactionStatus.SUCCESS
            )
            revenue = db.exec(stmt).one() or 0.0
            
            # Count rentals
            rental_count = db.exec(select(func.count(Rental.id)).where(Rental.start_station_id == station.id)).one() or 0
            
            results.append({
                "station_id": station.id,
                "station_name": station.name,
                "revenue": round(float(revenue), 2),
                "rental_count": rental_count
            })
            
        return sorted(results, key=lambda x: x["revenue"], reverse=True)

    @staticmethod
    def calculate_revenue_forecast(db: Session, days: int = 30) -> List[Dict[str, Any]]:
        """Projected revenue for next N days using simple moving average"""
        # Get last 30 days daily revenue
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=30)
        
        stmt = select(
            func.date(Transaction.created_at).label("date"),
            func.sum(Transaction.amount).label("daily_revenue")
        ).where(
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.created_at >= start_date
        ).group_by(func.date(Transaction.created_at)).order_by("date")
        
        history = db.exec(stmt).all()
        
        if not history:
            return []
            
        avg_daily = sum(h.daily_revenue for h in history) / len(history)
        
        forecast = []
        for i in range(1, days + 1):
            forecast_date = end_date + timedelta(days=i)
            # Add some variability or growth factor if desired
            forecast.append({
                "date": forecast_date,
                "projected_revenue": round(avg_daily, 2)
            })
            
        return forecast

    @staticmethod
    def get_profit_margins(db: Session, period: str = "30d") -> List[Dict[str, Any]]:
        """
        Margin analysis (Revenue vs REAL COGS: Battery depreciation + OpEx).
        """
        start, end, _, _, days = AnalyticsService._period_to_range(period)
        
        # 1. Revenue by station in period
        stations = db.exec(select(Station)).all()
        results = []
        
        for station in stations:
            # Sum rental revenue
            stmt = select(func.coalesce(func.sum(Transaction.amount), 0.0)).join(Rental, Rental.id == Transaction.rental_id).where(
                Rental.start_station_id == station.id,
                Transaction.status == TransactionStatus.SUCCESS,
                Transaction.created_at >= start,
                Transaction.created_at <= end
            )
            revenue = db.exec(stmt).one() or 0.0
            
            # 2. Calculate COGS (Depreciation)
            # Find batteries currently at this station or assigned to it
            # For simplicity, we calculate depreciation for all batteries associated with the station
            batteries = db.exec(select(Battery).where(Battery.station_id == station.id)).all()
            total_depreciation = 0.0
            for b in batteries:
                # Daily depreciation = Purchase Cost / 1000 days (approx 3 years)
                daily_dep = (b.purchase_cost or 25000.0) / 1000.0
                total_depreciation += daily_dep * days
                
            # 3. OpEx (Electricity, Maintenance) - Estimating 10% of revenue
            opex = revenue * 0.10
            
            total_cost = total_depreciation + opex
            margin_percent = round(((revenue - total_cost) / revenue * 100), 2) if revenue > 0 else 0.0
            
            results.append({
                "station_name": station.name,
                "revenue": round(revenue, 2),
                "cogs_depreciation": round(total_depreciation, 2),
                "opex": round(opex, 2),
                "total_cost": round(total_cost, 2),
                "margin_percentage": margin_percent
            })
            
        return results

    @staticmethod
    def get_profitability_forecast(db: Session, months: int = 6) -> List[Dict[str, Any]]:
        """
        Profitability forecast: Projected Revenue - Projected Costs.
        """
        # Get current monthly average
        revenue_history = AnalyticsService.calculate_revenue_forecast(db, months * 30)
        
        forecast = []
        # Estimate fixed monthly costs (all batteries * daily dep * 30)
        total_batteries = db.exec(select(Battery)).all()
        monthly_fixed_cost = sum((b.purchase_cost or 25000.0) / 1000.0 for b in total_batteries) * 30
        
        for i in range(months):
            # Sum projected revenue for that month (every 30 days)
            projected_rev = sum(item["projected_revenue"] for item in revenue_history[i*30 : (i+1)*30])
            # Projected OpEx (variable) = 15%
            projected_opex = projected_rev * 0.15
            
            proj_cost = monthly_fixed_cost + projected_opex
            proj_profit = projected_rev - proj_cost
            
            forecast.append({
                "month": (datetime.now(UTC) + timedelta(days=(i+1)*30)).strftime("%Y-%m"),
                "projected_revenue": round(projected_rev, 2),
                "projected_cost": round(proj_cost, 2),
                "projected_profit": round(proj_profit, 2),
                "margin": round((proj_profit / projected_rev * 100), 2) if projected_rev > 0 else 0.0
            })
            
        return forecast

    @staticmethod
    def get_platform_overview(db: Session, period: str = "30d") -> Dict[str, Any]:
        """Platform KPIs used by the admin dashboard (all values are real DB data)."""
        from app.models.user import User, UserType
        from app.models.support import SupportTicket, TicketStatus
        from app.models.battery import Battery, BatteryStatus
        from app.models.dealer import DealerProfile

        start, end, prev_start, prev_end, _ = AnalyticsService._period_to_range(period)

        def pct_change(current: float, previous: float) -> float:
            if previous == 0:
                return 0.0 if current == 0 else 100.0
            return round(((current - previous) / previous) * 100, 2)

        current_tx = and_(
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.created_at >= start,
            Transaction.created_at <= end,
        )
        previous_tx = and_(
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.created_at >= prev_start,
            Transaction.created_at <= prev_end,
        )
        revenue_current, revenue_previous = db.exec(
            select(
                func.coalesce(func.sum(case((current_tx, Transaction.amount), else_=0)), 0),
                func.coalesce(func.sum(case((previous_tx, Transaction.amount), else_=0)), 0),
            )
        ).one()
        revenue_current = float(revenue_current or 0.0)
        revenue_previous = float(revenue_previous or 0.0)

        current_rentals = and_(Rental.created_at >= start, Rental.created_at <= end)
        previous_rentals = and_(Rental.created_at >= prev_start, Rental.created_at <= prev_end)
        session_duration_minutes = (
            func.extract("epoch", Rental.end_time) - func.extract("epoch", Rental.start_time)
        ) / 60
        rentals_current, rentals_previous, active_rentals_now, avg_session_minutes = db.exec(
            select(
                func.coalesce(func.sum(case((current_rentals, 1), else_=0)), 0),
                func.coalesce(func.sum(case((previous_rentals, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Rental.status == RentalStatus.ACTIVE, 1), else_=0)), 0),
                func.avg(
                    case(
                        (
                            and_(
                                Rental.status == RentalStatus.COMPLETED,
                                Rental.end_time.is_not(None),
                                Rental.start_time >= start,
                            ),
                            session_duration_minutes,
                        ),
                        else_=None,
                    )
                ),
            )
        ).one()
        rentals_current = int(rentals_current or 0)
        rentals_previous = int(rentals_previous or 0)
        active_rentals_now = int(active_rentals_now or 0)
        avg_session_minutes = float(avg_session_minutes or 0.0)

        customer_current = and_(
            User.user_type == UserType.CUSTOMER,
            User.created_at >= start,
            User.created_at <= end,
        )
        customer_previous = and_(
            User.user_type == UserType.CUSTOMER,
            User.created_at >= prev_start,
            User.created_at <= prev_end,
        )
        total_users, new_users_current, new_users_prev = db.exec(
            select(
                func.coalesce(func.sum(case((User.user_type == UserType.CUSTOMER, 1), else_=0)), 0),
                func.coalesce(func.sum(case((customer_current, 1), else_=0)), 0),
                func.coalesce(func.sum(case((customer_previous, 1), else_=0)), 0),
            )
        ).one()
        total_users = int(total_users or 0)
        new_users_current = int(new_users_current or 0)
        new_users_prev = int(new_users_prev or 0)

        total_batteries, rented_batteries, avg_battery_health = db.exec(
            select(
                func.coalesce(func.count(Battery.id), 0),
                func.coalesce(func.sum(case((Battery.status == BatteryStatus.RENTED, 1), else_=0)), 0),
                func.avg(Battery.health_percentage),
            )
        ).one()
        total_batteries = int(total_batteries or 0)
        rented_batteries = int(rented_batteries or 0)
        avg_battery_health = float(avg_battery_health or 0.0)
        fleet_utilization = round((rented_batteries / total_batteries) * 100, 2) if total_batteries else 0.0

        active_stations = int(db.exec(select(func.count(Station.id))).one() or 0)
        active_dealers = int(db.exec(select(func.count(DealerProfile.id))).one() or 0)
        open_tickets = int(
            db.exec(
                select(func.count(SupportTicket.id)).where(SupportTicket.status == TicketStatus.OPEN)
            ).one()
            or 0
        )

        revenue_per_rental = (
            round(float(revenue_current) / rentals_current, 2) if rentals_current else 0.0
        )

        # Revenue sparkline (last 7 days)
        spark_stmt = (
            select(func.date(Transaction.created_at), func.sum(Transaction.amount))
            .where(
                Transaction.status == TransactionStatus.SUCCESS,
                Transaction.created_at >= end - timedelta(days=7),
            )
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )
        spark_rows = db.exec(spark_stmt).all()
        sparkline = [float(row[1]) for row in spark_rows] if spark_rows else []

        return {
            "total_revenue": {
                "label": "Total Revenue",
                "value": round(float(revenue_current), 2),
                "change_percent": pct_change(revenue_current, revenue_previous),
                "sparkline": sparkline,
            },
            "active_rentals": {
                "label": "Active Rentals",
                "value": active_rentals_now,
                "change_percent": pct_change(rentals_current, rentals_previous),
                "sparkline": [],
            },
            "total_users": {
                "label": "Total Users",
                "value": total_users,
                "change_percent": pct_change(new_users_current, new_users_prev),
                "sparkline": [],
            },
            "fleet_utilization": {
                "label": "Fleet Utilization",
                "value": fleet_utilization,
                "change_percent": 0.0,
                "sparkline": [],
            },
            "active_stations": {
                "label": "Active Stations",
                "value": active_stations,
                "change_percent": 0.0,
            },
            "active_dealers": {
                "label": "Active Dealers",
                "value": active_dealers,
                "change_percent": 0.0,
            },
            "avg_battery_health": {
                "label": "Avg. Battery Health",
                "value": round(float(avg_battery_health), 1),
                "change_percent": 0.0,
            },
            "open_tickets": {
                "label": "Open Tickets",
                "value": open_tickets,
                "change_percent": 0.0,
            },
            "revenue_per_rental": {
                "label": "Revenue per Rental",
                "value": revenue_per_rental,
                "change_percent": pct_change(revenue_per_rental, revenue_previous / max(rentals_previous, 1) if rentals_previous else 0.0),
            },
            "avg_session_duration": {
                "label": "Avg. Session",
                "value": avg_session_minutes,
                "change_percent": 0.0,
            },
        }

    @staticmethod
    def get_trends(db: Session, period: str = "daily") -> Dict[str, Any]:
        """Time-series trend data for revenue, rentals, active users, and battery health."""
        from app.models.battery_health import BatteryHealthSnapshot
        from app.models.user import User

        start_date, end_date, _, _, _ = AnalyticsService._period_to_range(period)

        # Rentals + active users per day
        rentals_stmt = (
            select(
                func.date(Rental.created_at).label("date"),
                func.count(Rental.id).label("rentals"),
                func.count(func.distinct(Rental.user_id)).label("users"),
            )
            .where(Rental.created_at >= start_date, Rental.created_at <= end_date)
            .group_by(func.date(Rental.created_at))
            .order_by(func.date(Rental.created_at))
        )
        rentals_rows = db.exec(rentals_stmt).all()
        rentals_map = {row.date: {"rentals": row.rentals, "users": row.users} for row in rentals_rows}

        # Revenue per day
        revenue_stmt = (
            select(
                func.date(Transaction.created_at).label("date"),
                func.sum(Transaction.amount).label("revenue"),
            )
            .where(
                Transaction.status == TransactionStatus.SUCCESS,
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
            )
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )
        revenue_rows = db.exec(revenue_stmt).all()
        revenue_map = {row.date: float(row.revenue) for row in revenue_rows}

        # Battery health per day (avg of snapshots)
        health_stmt = (
            select(
                func.date(BatteryHealthSnapshot.recorded_at).label("date"),
                func.avg(BatteryHealthSnapshot.health_percentage).label("health"),
            )
            .where(
                BatteryHealthSnapshot.recorded_at >= start_date,
                BatteryHealthSnapshot.recorded_at <= end_date,
            )
            .group_by(func.date(BatteryHealthSnapshot.recorded_at))
            .order_by(func.date(BatteryHealthSnapshot.recorded_at))
        )
        health_rows = db.exec(health_stmt).all()
        health_map = {row.date: float(row.health) for row in health_rows}

        # Union of all dates we have data for
        all_dates = sorted(
            set(list(rentals_map.keys()) + list(revenue_map.keys()) + list(health_map.keys()))
        )

        trends: List[Dict[str, Any]] = []
        for date_key in all_dates:
            rentals = rentals_map.get(date_key, {}).get("rentals", 0)
            users = rentals_map.get(date_key, {}).get("users", 0)
            trends.append(
                {
                    "date": date_key.isoformat(),
                    "rentals": rentals,
                    "revenue": round(revenue_map.get(date_key, 0.0), 2),
                    "users": users,
                    "battery_health": round(health_map.get(date_key, 0.0), 2),
                }
            )

        return {"period": period, "data": trends}

    @staticmethod
    def get_conversion_funnel(db: Session) -> Dict[str, Any]:
        """Funnel: installs → registrations → KYC verified → first rental (with conversions)."""
        from app.models.user import User, UserType
        from app.models.kyc import KYCRecord

        def build_stage(name: str, count: int, prev: Optional[int]) -> Dict[str, Any]:
            conversion = 100.0 if prev in (None, 0) else round((count / prev) * 100, 2)
            drop = round(100 - conversion, 2) if prev not in (None, 0) else 0.0
            return {
                "stage": name,
                "count": count,
                "conversion_rate": conversion,
                "drop_off_rate": drop,
            }

        total_users = (
            db.exec(select(func.count(User.id)).where(User.user_type == UserType.CUSTOMER)).one()
            or 0
        )

        installs = int(total_users * 1.15) + 50  # lightweight estimate
        registrations = total_users
        kyc_verified = (
            db.exec(
                select(func.count(KYCRecord.id)).where(
                    KYCRecord.status == "verified"
                )
            ).one()
            or 0
        )
        first_rental = (
            db.exec(select(func.count(func.distinct(Rental.user_id)))).one() or 0
        )

        stages = [
            build_stage("App Installs", installs, None),
            build_stage("Registrations", registrations, installs),
            build_stage("KYC Verified", kyc_verified, registrations),
            build_stage("First Rental", first_rental, kyc_verified or registrations),
        ]

        return {"stages": stages}

    @staticmethod
    def get_user_behavior(db: Session) -> Dict[str, Any]:
        """Aggregated user behavior: session duration, rentals/user, peak hours, heatmap."""
        from app.models.user import User, UserType

        lookback = datetime.now(UTC) - timedelta(days=60)
        rentals = db.exec(
            select(Rental).where(Rental.created_at >= lookback)
        ).all()

        durations = [
            (r.end_time - r.start_time).total_seconds() / 60
            for r in rentals
            if r.start_time and r.end_time
        ]
        avg_session = round(sum(durations) / len(durations), 2) if durations else 0.0

        distinct_users = {r.user_id for r in rentals}
        avg_rentals_per_user = round(len(rentals) / len(distinct_users), 2) if distinct_users else 0.0

        # Peak hours (top 3)
        hour_counter: Counter = Counter()
        heatmap = [[0 for _ in range(24)] for _ in range(7)]
        for r in rentals:
            hour = r.created_at.hour
            dow = r.created_at.weekday()  # Monday=0
            hour_counter[hour] += 1
            heatmap[dow][hour] += 1
        top_hours = hour_counter.most_common(3)
        peak_hours = {f"{h:02d}:00": count for h, count in top_hours}

        # Session histogram buckets (in minutes)
        bucket_labels = [("0-5m", 0, 5), ("5-10m", 5, 10), ("10-20m", 10, 20), ("20-40m", 20, 40), ("40m+", 40, None)]
        histogram = []
        for label, low, high in bucket_labels:
            count = len([d for d in durations if (d >= low and (high is None or d < high))])
            histogram.append({"range": label, "count": count})

        # Cohort breakdown: users created in last 30d vs older that were active in rentals
        cutoff = datetime.now(UTC) - timedelta(days=30)
        new_users = db.exec(
            select(func.count(User.id)).where(
                User.user_type == UserType.CUSTOMER,
                User.created_at >= cutoff,
            )
        ).one() or 0
        returning_users = max(len(distinct_users) - new_users, 0)
        total_users = new_users + returning_users or 1

        cohort_breakdown = {
            "New Users": round((new_users / total_users) * 100, 1),
            "Returning Users": round((returning_users / total_users) * 100, 1),
        }

        return {
            "avg_session_duration": avg_session,
            "avg_rentals_per_user": avg_rentals_per_user,
            "peak_hours": peak_hours,
            "heatmap": heatmap,
            "session_histogram": histogram,
            "cohort_breakdown": cohort_breakdown,
        }

    @staticmethod
    def get_recent_activity(db: Session, activity_type: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """Recent activity across rentals, payments, and support events."""
        from app.models.support import SupportTicket

        def _enum_text(value: Any, fallback: str = "unknown") -> str:
            if value is None:
                return fallback
            if hasattr(value, "value"):
                return str(value.value)
            return str(value)

        activities: List[Dict[str, Any]] = []

        rentals = db.exec(
            select(Rental).order_by(Rental.created_at.desc()).limit(limit * 2)
        ).all()
        for r in rentals:
            rental_status = _enum_text(r.status)
            activities.append(
                {
                    "title": "Rental Started" if r.status == RentalStatus.ACTIVE else f"Rental {rental_status}",
                    "description": f"User {r.user_id} at station {r.start_station_id}",
                    "time": r.created_at.strftime("%b %d, %H:%M"),
                    "type": "rental",
                    "severity": "info" if r.status == RentalStatus.ACTIVE else "low",
                    "timestamp": r.created_at,
                    "details": {
                        "rental_id": r.id,
                        "battery_id": r.battery_id,
                        "amount": r.total_amount,
                    },
                }
            )

        transactions = db.exec(
            select(Transaction)
            .where(Transaction.status == TransactionStatus.SUCCESS)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        ).all()
        for t in transactions:
            activities.append(
                {
                    "title": "Payment Successful",
                    "description": f"₹{t.amount} via {t.payment_method}",
                    "time": t.created_at.strftime("%b %d, %H:%M"),
                    "type": "payment",
                    "severity": "success",
                    "timestamp": t.created_at,
                    "details": {"transaction_id": t.id, "user_id": t.user_id},
                }
            )

        tickets = db.exec(
            select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(limit)
        ).all()
        for ticket in tickets:
            priority = _enum_text(ticket.priority)
            severity = "critical" if priority in {"high", "critical"} else "medium"
            activities.append(
                {
                    "title": f"Support: {ticket.subject}",
                    "description": f"Priority {priority}",
                    "time": ticket.created_at.strftime("%b %d, %H:%M"),
                    "type": "alert",
                    "severity": severity,
                    "timestamp": ticket.created_at,
                    "details": {"ticket_id": ticket.id, "status": _enum_text(ticket.status)},
                }
            )

        # Sort and filter
        activities.sort(key=lambda a: a["timestamp"], reverse=True)
        if activity_type and activity_type != "all":
            activities = [a for a in activities if a["type"] == activity_type]

        trimmed = activities[:limit]
        for item in trimmed:
            item.pop("timestamp", None)
        return {"activities": trimmed}

    @staticmethod
    def get_top_stations(db: Session) -> Dict[str, Any]:
        """Top stations formatted for the dashboard (revenue + utilization + sparkline)."""
        stations = db.exec(select(Station)).all()
        station_ids = [station.id for station in stations if station.id is not None]
        station_data: List[Dict[str, Any]] = []

        rental_counts = {
            row[0]: int(row[1] or 0)
            for row in db.exec(
                select(Rental.start_station_id, func.count(Rental.id))
                .where(Rental.start_station_id.in_(station_ids))
                .group_by(Rental.start_station_id)
            ).all()
        } if station_ids else {}
        revenue_map = {
            row[0]: float(row[1] or 0.0)
            for row in db.exec(
                select(Rental.start_station_id, func.coalesce(func.sum(Transaction.amount), 0))
                .join(Transaction, Transaction.rental_id == Rental.id)
                .where(
                    Rental.start_station_id.in_(station_ids),
                    Transaction.status == TransactionStatus.SUCCESS,
                )
                .group_by(Rental.start_station_id)
            ).all()
        } if station_ids else {}

        slot_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        if station_ids:
            for station_id, slot_status, count in db.exec(
                select(StationSlot.station_id, StationSlot.status, func.count(StationSlot.id))
                .where(StationSlot.station_id.in_(station_ids))
                .group_by(StationSlot.station_id, StationSlot.status)
            ).all():
                slot_counts[station_id][str(slot_status)] = int(count or 0)

        sparkline_map: Dict[int, List[int]] = defaultdict(list)
        if station_ids:
            for station_id, _, count in db.exec(
                select(
                    Rental.start_station_id,
                    func.date(Rental.created_at),
                    func.count(Rental.id),
                )
                .where(
                    Rental.start_station_id.in_(station_ids),
                    Rental.created_at >= datetime.now(UTC) - timedelta(days=7),
                )
                .group_by(Rental.start_station_id, func.date(Rental.created_at))
                .order_by(Rental.start_station_id, func.date(Rental.created_at))
            ).all():
                sparkline_map[station_id].append(int(count or 0))

        for station in stations:
            station_id = station.id
            rental_count = rental_counts.get(station_id, 0)
            revenue = revenue_map.get(station_id, 0.0)

            status_counts = slot_counts.get(station_id, {})
            total_slots = station.total_slots or sum(status_counts.values()) or 1
            available = status_counts.get("ready", 0) + status_counts.get("empty", 0)
            charging = status_counts.get("charging", 0)
            offline = status_counts.get("error", 0) + status_counts.get("maintenance", 0)

            utilization = round((rental_count / (total_slots * 30)) * 100, 2) if total_slots else 0
            rating = station.rating if station.rating and station.rating > 0 else 0.0
            spark = sparkline_map.get(station_id, [])

            station_data.append(
                {
                    "id": str(station.id),
                    "name": station.name,
                    "location": station.city or station.address,
                    "rentals": rental_count,
                    "revenue": round(float(revenue), 2),
                    "utilization": utilization,
                    "rating": rating,
                    "available_percent": round((available / total_slots) * 100, 1),
                    "charging_percent": round((charging / total_slots) * 100, 1),
                    "offline_percent": round((offline / total_slots) * 100, 1),
                    "sparkline": spark,
                }
            )

        station_data.sort(key=lambda s: s["revenue"], reverse=True)
        return {"stations": station_data[:10]}

    @staticmethod
    def get_battery_health_distribution(db: Session) -> Dict[str, Any]:
        """Distribution of all batteries by health % range (with previous window)."""
        from app.models.battery_health import BatteryHealthSnapshot

        now = datetime.now(UTC)
        prev_start = now - timedelta(days=60)
        prev_end = now - timedelta(days=30)

        bucket_labels = [
            "Excellent (90-100%)",
            "Good (80-89%)",
            "Fair (70-79%)",
            "Critical (<70%)",
        ]
        current_counts = db.exec(
            select(
                func.coalesce(func.sum(case((Battery.health_percentage >= 90, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (and_(Battery.health_percentage >= 80, Battery.health_percentage < 90), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (and_(Battery.health_percentage >= 70, Battery.health_percentage < 80), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((Battery.health_percentage < 70, 1), else_=0)), 0),
            )
        ).one()
        previous_counts = db.exec(
            select(
                func.coalesce(func.sum(case((BatteryHealthSnapshot.health_percentage >= 90, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    BatteryHealthSnapshot.health_percentage >= 80,
                                    BatteryHealthSnapshot.health_percentage < 90,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    BatteryHealthSnapshot.health_percentage >= 70,
                                    BatteryHealthSnapshot.health_percentage < 80,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((BatteryHealthSnapshot.health_percentage < 70, 1), else_=0)), 0),
            ).where(
                BatteryHealthSnapshot.recorded_at >= prev_start,
                BatteryHealthSnapshot.recorded_at <= prev_end,
            )
        ).one()

        buckets = {label: int(count or 0) for label, count in zip(bucket_labels, current_counts)}
        previous_buckets = {label: int(count or 0) for label, count in zip(bucket_labels, previous_counts)}
        total = sum(buckets.values()) or 1
        prev_total = sum(previous_buckets.values()) or total

        def to_list(data: Dict[str, int]) -> List[Dict[str, Any]]:
            total_for_percent = sum(data.values()) or 1
            return [
                {
                    "category": name,
                    "count": count,
                    "percentage": round((count / total_for_percent) * 100, 1),
                }
                for name, count in data.items()
                if count > 0
            ]

        return {
            "total": total,
            "previous_total": prev_total,
            "distribution": to_list(buckets),
            "previous_distribution": to_list(previous_buckets) if previous_buckets else [],
        }

    @staticmethod
    def get_demand_forecast_per_station(db: Session) -> Dict[str, Any]:
        """7-day demand forecast (platform-wide), with actuals from the last week."""
        today = datetime.now(UTC).date()
        lookback_start = today - timedelta(days=14)

        rentals = db.exec(
            select(func.date(Rental.created_at), func.count(Rental.id))
            .where(Rental.created_at >= lookback_start)
            .group_by(func.date(Rental.created_at))
        ).all()
        rental_map = {row[0]: row[1] for row in rentals}
        avg_daily = (sum(rental_map.values()) / len(rental_map)) if rental_map else 0

        forecast: List[Dict[str, Any]] = []
        for i in range(7):
            day = today + timedelta(days=i)
            forecast.append(
                {
                    "date": day.isoformat(),
                    "predicted": round(avg_daily * (1.05 if i > 2 else 1.0), 2),
                    "actual": float(rental_map.get(day, 0)) if day <= today else None,
                }
            )

        return {"forecast": forecast}
    @staticmethod
    def get_customer_dashboard(user_id: int, db: Session) -> Dict[str, Any]:
        """Aggregated stats for customer home screen"""
        from app.models.user import User
        from app.models.rental import Rental
        from app.models.membership import Membership
        from app.models.financial import Transaction, TransactionStatus
        
        user = db.get(User, user_id)
        if not user:
            return {}
            
        # 1. Wallet Balance
        wallet_balance = user.wallet.balance if user.wallet else 0.0
        
        # 2. Active Rental
        active_rental = db.exec(
            select(Rental).where(Rental.user_id == user_id, Rental.status == "active")
        ).first()
        
        # 3. Membership & Points
        membership = db.exec(
            select(Membership).where(Membership.user_id == user_id)
        ).first()
        
        points = membership.points_balance if membership else 0
        tier = membership.tier if membership else "basic"
        
        # 4. Recent Transactions (optional but helpful)
        recent_tx = db.exec(
            select(Transaction).where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc()).limit(5)
        ).all()
        
        return {
            "wallet_balance": round(wallet_balance, 2),
            "active_rental_id": active_rental.id if active_rental else None,
            "active_rental_status": active_rental.status if active_rental else None,
            "points_balance": points,
            "membership_tier": tier,
            "recent_transactions": [
                {"id": t.id, "amount": t.amount, "type": t.transaction_type, "status": t.status}
                for t in recent_tx
            ]
        }

    @staticmethod
    def get_revenue_by_region(db: Session) -> List[Dict[str, Any]]:
        """Revenue by city/region based on station locations"""
        from app.models.station import Station
        from app.models.rental import Rental
        from app.models.financial import Transaction, TransactionStatus
        
        # Simple grouping by city
        stmt = (
            select(
                Station.city,
                func.sum(Transaction.amount),
                func.count(Rental.id),
            )
            .join(Rental, Rental.start_station_id == Station.id)
            .join(Transaction, Transaction.rental_id == Rental.id)
            .where(Transaction.status == TransactionStatus.SUCCESS)
            .group_by(Station.city)
        )
        results = db.execute(stmt).all()
        
        return [
            {
                "region": r[0] or "Unknown",
                "revenue": round(float(r[1] or 0.0), 2),
                "rental_count": int(r[2] or 0),
            }
            for r in results
        ]

    @staticmethod
    def get_user_growth(db: Session, period: str) -> List[Dict[str, Any]]:
        """New users per period"""
        from app.models.user import User
        
        start_date = datetime.now(UTC) - timedelta(days=180)
        group_func = (
            func.date_trunc("month", User.created_at)
            if period == "monthly"
            else func.date_trunc("week", User.created_at)
        )

        new_users_rows = (
            db.execute(
                select(group_func, func.count(User.id))
                .where(User.created_at >= start_date)
                .group_by(group_func)
                .order_by(group_func)
            ).all()
        )

        rental_group_func = (
            func.date_trunc("month", Rental.created_at)
            if period == "monthly"
            else func.date_trunc("week", Rental.created_at)
        )
        rental_rows = (
            db.execute(
                select(
                    rental_group_func,
                    func.count(func.distinct(Rental.user_id)),
                )
                .where(Rental.created_at >= start_date)
                .group_by(rental_group_func)
            ).all()
        )
        rental_map = {row[0]: row[1] for row in rental_rows}

        growth = []
        for row in new_users_rows:
            bucket = row[0]
            new_users = int(row[1] or 0)
            returning_users = max(int(rental_map.get(bucket, 0)) - new_users, 0)
            growth.append(
                {
                    "period": bucket.isoformat(),
                    "new_users": new_users,
                    "returning_users": returning_users,
                    "total_users": new_users + returning_users,
                }
            )
        return growth

    @staticmethod
    def get_revenue_by_station_detailed(db: Session, period: str = "30d") -> Dict[str, Any]:
        """Revenue distribution by station with rental counts and battery mix."""
        from app.models.battery import Battery

        start, end, _, _, _ = AnalyticsService._period_to_range(period)
        stations = db.exec(select(Station)).all()
        station_ids = [station.id for station in stations if station.id is not None]

        station_rows: List[Dict[str, Any]] = []
        total_revenue = 0.0

        duration_minutes = (
            func.extract("epoch", Rental.end_time) - func.extract("epoch", Rental.start_time)
        ) / 60
        rental_stats = {
            row[0]: {
                "rental_count": int(row[1] or 0),
                "avg_session_duration": round(float(row[2] or 0.0), 2),
            }
            for row in db.exec(
                select(
                    Rental.start_station_id,
                    func.count(Rental.id),
                    func.avg(
                        case(
                            (
                                and_(Rental.end_time.is_not(None), Rental.start_time.is_not(None)),
                                duration_minutes,
                            ),
                            else_=None,
                        )
                    ),
                )
                .where(
                    Rental.start_station_id.in_(station_ids),
                    Rental.created_at >= start,
                    Rental.created_at <= end,
                )
                .group_by(Rental.start_station_id)
            ).all()
        } if station_ids else {}

        revenue_map = {
            row[0]: float(row[1] or 0.0)
            for row in db.exec(
                select(Rental.start_station_id, func.coalesce(func.sum(Transaction.amount), 0))
                .join(Transaction, Transaction.rental_id == Rental.id)
                .where(
                    Rental.start_station_id.in_(station_ids),
                    Transaction.status == TransactionStatus.SUCCESS,
                    Transaction.created_at >= start,
                    Transaction.created_at <= end,
                )
                .group_by(Rental.start_station_id)
            ).all()
        } if station_ids else {}
        fallback_revenue_map = {
            row[0]: float(row[1] or 0.0)
            for row in db.exec(
                select(Rental.start_station_id, func.coalesce(func.sum(Rental.total_amount), 0))
                .where(
                    Rental.start_station_id.in_(station_ids),
                    Rental.created_at >= start,
                    Rental.created_at <= end,
                )
                .group_by(Rental.start_station_id)
            ).all()
        } if station_ids else {}

        battery_mix_map: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        if station_ids:
            for station_id, battery_type, revenue, rental_count in db.exec(
                select(
                    Rental.start_station_id,
                    Battery.battery_type,
                    func.coalesce(func.sum(Transaction.amount), 0),
                    func.count(Transaction.id),
                )
                .join(Transaction, Transaction.rental_id == Rental.id)
                .join(Battery, Battery.id == Rental.battery_id)
                .where(
                    Rental.start_station_id.in_(station_ids),
                    Transaction.status == TransactionStatus.SUCCESS,
                    Transaction.created_at >= start,
                    Transaction.created_at <= end,
                )
                .group_by(Rental.start_station_id, Battery.battery_type)
            ).all():
                battery_mix_map[station_id].append(
                    {
                        "type": battery_type or "Unknown",
                        "revenue": float(revenue or 0.0),
                        "percentage": 0,
                        "rental_count": int(rental_count or 0),
                    }
                )

        for station in stations:
            stats = rental_stats.get(station.id, {"rental_count": 0, "avg_session_duration": 0.0})
            revenue = revenue_map.get(station.id, 0.0) or fallback_revenue_map.get(station.id, 0.0)
            battery_mix = battery_mix_map.get(station.id, [])

            station_rows.append(
                {
                    "station_name": station.name,
                    "rental_count": stats["rental_count"],
                    "revenue": round(float(revenue), 2),
                    "percentage": 0,  # filled later
                    "avg_session_duration": stats["avg_session_duration"],
                    "battery_mix": battery_mix,
                    "utilization": (
                        (station.available_batteries or 0) / station.total_slots * 100
                        if station.total_slots
                        else 0
                    ),
                }
            )
            total_revenue += float(revenue)

        # fill percentages
        for row in station_rows:
            row["percentage"] = (
                round((row["revenue"] / total_revenue) * 100, 2) if total_revenue else 0
            )
            for mix in row["battery_mix"]:
                mix["percentage"] = (
                    round((mix["revenue"] / row["revenue"]) * 100, 2)
                    if row["revenue"]
                    else 0
                )

        return {"total_revenue": round(total_revenue, 2), "stations": station_rows}

    @staticmethod
    def get_revenue_by_battery_type(db: Session, period: str = "30d") -> Dict[str, Any]:
        """Revenue split by battery chemistry/model and by station."""
        from app.models.battery import Battery

        start, end, _, _, _ = AnalyticsService._period_to_range(period)

        type_rows = db.exec(
            select(
                Battery.battery_type,
                func.coalesce(func.sum(Transaction.amount), 0),
                func.count(Transaction.id),
            )
            .join(Rental, Rental.id == Transaction.rental_id, isouter=True)
            .join(Battery, Battery.id == Rental.battery_id, isouter=True)
            .where(
                Transaction.status == TransactionStatus.SUCCESS,
                Transaction.created_at >= start,
                Transaction.created_at <= end,
            )
            .group_by(Battery.battery_type)
        ).all()

        total_revenue = sum(float(row[1] or 0) for row in type_rows) or 1
        types = [
            {
                "type": row[0] or "Unknown",
                "revenue": float(row[1] or 0),
                "percentage": round((float(row[1] or 0) / total_revenue) * 100, 2),
                "rental_count": int(row[2] or 0),
            }
            for row in type_rows
        ]

        # Station mix breakdown
        station_mix = []
        stations = db.exec(select(Station)).all()
        for station in stations:
            mix_rows = db.exec(
                select(
                    Battery.battery_type,
                    func.coalesce(func.sum(Transaction.amount), 0),
                )
                .join(Rental, Rental.id == Transaction.rental_id, isouter=True)
                .join(Battery, Battery.id == Rental.battery_id, isouter=True)
                .where(
                    Rental.start_station_id == station.id,
                    Transaction.status == TransactionStatus.SUCCESS,
                    Transaction.created_at >= start,
                    Transaction.created_at <= end,
                )
                .group_by(Battery.battery_type)
            ).all()
            if not mix_rows:
                continue
            station_mix.append(
                {
                    "station_name": station.name,
                    "battery_mix": [
                        {
                            "type": row[0] or "Unknown",
                            "revenue": float(row[1] or 0),
                            "percentage": 0,  # filled later
                            "rental_count": 0,
                        }
                        for row in mix_rows
                    ],
                }
            )
            for mix in station_mix[-1]["battery_mix"]:
                station_total = sum(m["revenue"] for m in station_mix[-1]["battery_mix"]) or 1
                mix["percentage"] = round((mix["revenue"] / station_total) * 100, 2)

        return {"types": types, "station_mix": station_mix}

    @staticmethod
    def get_fleet_inventory_status(db: Session) -> Dict[str, Any]:
        """Fleet health and utilization overview"""
        from app.models.battery import Battery, BatteryStatus

        items: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "available": 0, "rented": 0, "maintenance": 0, "charging": 0}
        )

        for battery_type, battery_status, count in db.exec(
            select(Battery.battery_type, Battery.status, func.count(Battery.id)).group_by(
                Battery.battery_type, Battery.status
            )
        ).all():
            key = battery_type or "Unknown"
            status_value = battery_status.value if hasattr(battery_status, "value") else str(battery_status)
            quantity = int(count or 0)
            items[key]["total"] += quantity
            if status_value == BatteryStatus.AVAILABLE.value:
                items[key]["available"] += quantity
            elif status_value == BatteryStatus.RENTED.value:
                items[key]["rented"] += quantity
            elif status_value == BatteryStatus.MAINTENANCE.value:
                items[key]["maintenance"] += quantity
            elif status_value == BatteryStatus.CHARGING.value:
                items[key]["charging"] += quantity

        total_batteries = sum(v["total"] for v in items.values())
        total_available = sum(v["available"] for v in items.values())
        total_rented = sum(v["rented"] for v in items.values())
        total_maintenance = sum(v["maintenance"] for v in items.values())
        total_charging = sum(v["charging"] for v in items.values())

        inventory_list = [
            {
                "category": k,
                "total": v["total"],
                "available": v["available"],
                "rented": v["rented"],
                "maintenance": v["maintenance"],
                "charging": v["charging"],
            }
            for k, v in items.items()
        ]

        return {
            "total_batteries": total_batteries,
            "total_available": total_available,
            "inventory": inventory_list,
            "status_breakdown": {
                "rented": total_rented,
                "charging": total_charging,
                "available": total_available,
            },
            "utilization_rate": round((total_rented / total_batteries * 100), 1)
            if total_batteries
            else 0,
        }
