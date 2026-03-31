from sqlmodel import Session, select, func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.rental import Rental
from app.models.station import Station
import math

class AnalyticsService:
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
        end_date = datetime.utcnow()
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
    def get_profit_margins(db: Session) -> List[Dict[str, Any]]:
        """Margin analysis (simplified revenue vs estimated operational cost)"""
        # This usually requires a Expense model. Mocking costs as % of revenue for demo.
        revenue_by_station = AnalyticsService.get_revenue_by_station(db)
        
        margins = []
        for s in revenue_by_station:
            # Assume 60% operational efficiency (40% cost)
            est_cost = s["revenue"] * 0.4
            margins.append({
                "category": s["station_name"],
                "revenue": s["revenue"],
                "estimated_cost": round(est_cost, 2),
                "margin_percentage": 60.0
            })
            
        return margins

    @staticmethod
    def get_platform_overview(db: Session) -> Dict[str, Any]:
        """Platform KPIs: active users, total rentals, revenue today"""
        from app.models.user import User
        from app.models.rental import Rental
        from app.models.financial import Transaction, TransactionStatus
        from datetime import datetime
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        active_users = db.exec(select(func.count(User.id)).where(User.is_active == True)).one()
        total_rentals = db.exec(select(func.count(Rental.id))).one()
        revenue_today = db.exec(
            select(func.sum(Transaction.amount))
            .where(Transaction.status == TransactionStatus.SUCCESS, Transaction.created_at >= today_start)
        ).one() or 0.0
        
        return {
            "active_users": active_users,
            "total_rentals": total_rentals,
            "revenue_today": round(float(revenue_today), 2)
        }

    @staticmethod
    def get_trends(db: Session, period: str = "daily") -> List[Dict[str, Any]]:
        """Daily/weekly/monthly trend data for rentals and revenue"""
        from app.models.rental import Rental
        from app.models.financial import Transaction, TransactionStatus
        
        # Default to daily for last 30 days
        days = 30
        if period == "weekly": days = 90
        elif period == "monthly": days = 365
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Rentals trend
        rental_stmt = select(
            func.date(Rental.created_at).label("date"),
            func.count(Rental.id).label("count")
        ).where(Rental.created_at >= start_date).group_by(func.date(Rental.created_at)).order_by("date")
        rental_trend = db.exec(rental_stmt).all()
        
        # Revenue trend
        rev_stmt = select(
            func.date(Transaction.created_at).label("date"),
            func.sum(Transaction.amount).label("revenue")
        ).where(
            Transaction.status == TransactionStatus.SUCCESS, 
            Transaction.created_at >= start_date
        ).group_by(func.date(Transaction.created_at)).order_by("date")
        rev_trend = db.exec(rev_stmt).all()
        
        # Merge results
        trends = []
        rev_map = {r[0]: r[1] for r in rev_trend}
        for r in rental_trend:
            trends.append({
                "date": r[0],
                "rentals": r[1],
                "revenue": round(float(rev_map.get(r[0], 0.0)), 2)
            })
        return trends

    @staticmethod
    def get_conversion_funnel(db: Session) -> Dict[str, Any]:
        """Funnel: installs → registrations → first rental with drop-off %"""
        from app.models.user import User
        from app.models.rental import Rental
        
        # Mocking 'installs' as users with no verified email yet or just total users * 1.5
        total_users = db.exec(select(func.count(User.id))).one()
        installs = int(total_users * 1.3) # Estimated
        registrations = total_users
        
        # Users who have at least one rental
        users_with_rental = db.exec(select(func.count(func.distinct(Rental.user_id)))).one()
        
        return {
            "installs": installs,
            "registrations": registrations,
            "first_rental": users_with_rental,
            "drop_off_pct": {
                "install_to_reg": round((1 - registrations/installs)*100, 1) if installs else 0,
                "reg_to_rental": round((1 - users_with_rental/registrations)*100, 1) if registrations else 0
            }
        }

    @staticmethod
    def get_user_behavior(db: Session) -> Dict[str, Any]:
        """Aggregated user behavior: avg session, popular stations, peak hours"""
        from app.models.rental import Rental
        from app.models.station import Station
        
        # Avg session duration (completed rentals)
        completed = db.exec(select(Rental).where(Rental.status == "completed")).all()
        durations = [(r.actual_end_time - r.start_time).total_seconds() / 60 for r in completed if r.actual_end_time]
        avg_session = sum(durations) / len(durations) if durations else 0
        
        # Popular stations
        stmt = select(Station.name, func.count(Rental.id)).join(Rental, Rental.start_station_id == Station.id).group_by(Station.name).order_by(func.count(Rental.id).desc()).limit(5)
        popular_stations = db.exec(stmt).all()
        
        # Peak hours (hour of day 0-23)
        peak_stmt = select(func.extract('hour', Rental.created_at), func.count(Rental.id)).group_by(func.extract('hour', Rental.created_at)).order_by(func.count(Rental.id).desc()).limit(3)
        peak_hours = db.exec(peak_stmt).all()
        
        return {
            "avg_session_minutes": round(avg_session, 1),
            "popular_stations": [{"name": r[0], "rentals": r[1]} for r in popular_stations],
            "peak_hours": [int(r[0]) for r in peak_hours]
        }

    @staticmethod
    def get_battery_health_distribution(db: Session) -> Dict[str, Any]:
        """Distribution of all batteries by health % range"""
        from app.models.battery import Battery
        
        bins = {
            "90-100%": 0,
            "80-89%": 0,
            "70-79%": 0,
            "<70%": 0
        }
        
        batteries = db.exec(select(Battery)).all()
        for b in batteries:
            soh = b.soh or 100.0
            if soh >= 90: bins["90-100%"] += 1
            elif soh >= 80: bins["80-89%"] += 1
            elif soh >= 70: bins["70-79%"] += 1
            else: bins["<70%"] += 1
            
        return bins

    @staticmethod
    def get_demand_forecast_per_station(db: Session) -> List[Dict[str, Any]]:
        """30-day demand forecast per station"""
        from app.models.station import Station
        from app.models.rental import Rental
        
        stations = db.exec(select(Station)).all()
        forecasts = []
        
        for s in stations:
            # Simple average of last 14 days * historical growth factor
            stmt = select(func.count(Rental.id)).where(Rental.start_station_id == s.id, Rental.created_at >= (datetime.utcnow() - timedelta(days=14)))
            last_14_days = db.exec(stmt).one() or 0
            daily_avg = last_14_days / 14
            
            forecasts.append({
                "station_id": s.id,
                "station_name": s.name,
                "projected_30d_demand": math.ceil(daily_avg * 30 * 1.1) # 10% growth factor
            })
            
        return forecasts
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
        stmt = select(Station.city, func.sum(Transaction.amount)).join(Rental, Rental.start_station_id == Station.id).join(Transaction, Transaction.rental_id == Rental.id).where(Transaction.status == TransactionStatus.SUCCESS).group_by(Station.city)
        results = db.execute(stmt).all()
        
        return [{"region": r[0], "revenue": round(float(r[1]), 2)} for r in results]

    @staticmethod
    def get_user_growth(db: Session, period: str) -> List[Dict[str, Any]]:
        """New users per period"""
        from app.models.user import User
        
        # Default to last 6 months
        start_date = datetime.utcnow() - timedelta(days=180)
        
        group_func = func.date_trunc('month', User.created_at) if period == "monthly" else func.date_trunc('week', User.created_at)
        
        stmt = select(group_func, func.count(User.id)).where(User.created_at >= start_date).group_by(group_func).order_by(group_func)
        results = db.execute(stmt).all()
        
        return [{"period": r[0].isoformat(), "new_users": r[1]} for r in results]

    @staticmethod
    def get_fleet_inventory_status(db: Session) -> Dict[str, Any]:
        """Fleet health and utilization overview"""
        from app.models.battery import Battery
        from app.models.station import StationSlot
        
        total_batteries = db.exec(select(func.count(Battery.id))).one()
        in_rental = db.exec(select(func.count(Battery.id)).where(Battery.status == "rented")).one()
        in_charging = db.exec(select(func.count(StationSlot.id)).where(StationSlot.status == "charging")).one()
        
        health_dist = AnalyticsService.get_battery_health_distribution(db)
        
        return {
            "total_batteries": total_batteries,
            "utilization_rate": round((in_rental / total_batteries * 100), 1) if total_batteries > 0 else 0,
            "status_breakdown": {
                "rented": in_rental,
                "charging": in_charging,
                "available": total_batteries - in_rental - in_charging
            },
            "health_distribution": health_dist
        }

    # ─── Personal Cost Analytics (Task 7) ───────────────────────────

    @staticmethod
    def _resolve_period_dates(period: str):
        """Convert a period string (3m|6m|1y|all) into (start_date, end_date) for
        the *current* window and the equivalent *previous* window."""
        from dateutil.relativedelta import relativedelta

        now = datetime.utcnow()
        if period == "3m":
            delta = relativedelta(months=3)
        elif period == "6m":
            delta = relativedelta(months=6)
        elif period == "1y":
            delta = relativedelta(years=1)
        else:  # "all"
            # Use a very early date for "all"
            return datetime(2000, 1, 1), now, datetime(2000, 1, 1), datetime(2000, 1, 1)

        current_start = now - delta
        previous_start = current_start - delta
        return current_start, now, previous_start, current_start

    @staticmethod
    def _sum_rental_spending(db: Session, user_id: int, start: datetime, end: datetime) -> float:
        """Sum successful rental_payment transactions for a user in range."""
        stmt = select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.RENTAL_PAYMENT,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.created_at >= start,
            Transaction.created_at <= end,
        )
        return float(db.exec(stmt).one())

    @staticmethod
    def _sum_purchase_spending(db: Session, user_id: int, start: datetime, end: datetime) -> float:
        """Sum purchase amounts for a user in range (from Purchase model)."""
        from app.models.rental import Purchase
        stmt = select(func.coalesce(func.sum(Purchase.amount), 0.0)).where(
            Purchase.user_id == user_id,
            Purchase.timestamp >= start,
            Purchase.timestamp <= end,
        )
        return float(db.exec(stmt).one())

    @staticmethod
    def get_personal_cost_analytics(
        db: Session,
        user_id: int,
        period: str = "3m",
        transaction_type: str = "all",
    ) -> dict:
        """Full personal cost analytics for a customer.

        Returns total_spent_this_month, this_year, lifetime, avg_monthly,
        breakdown, month-over-month change, inline trends, and period comparison.
        """
        from dateutil.relativedelta import relativedelta

        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        lifetime_start = datetime(2000, 1, 1)
        prev_month_start = month_start - relativedelta(months=1)

        # --- lifetime / year / month totals ---
        include_rental = transaction_type in ("rental", "all")
        include_purchase = transaction_type in ("purchase", "all")

        def _range_total(start, end):
            total = 0.0
            if include_rental:
                total += AnalyticsService._sum_rental_spending(db, user_id, start, end)
            if include_purchase:
                total += AnalyticsService._sum_purchase_spending(db, user_id, start, end)
            return round(total, 2)

        total_lifetime = _range_total(lifetime_start, now)
        total_year = _range_total(year_start, now)
        total_month = _range_total(month_start, now)
        total_prev_month = _range_total(prev_month_start, month_start)

        # avg monthly (over the requested period window)
        current_start, current_end, prev_start, prev_end = AnalyticsService._resolve_period_dates(period)
        period_total = _range_total(current_start, current_end)
        months_in_period = max(
            1,
            (current_end.year - current_start.year) * 12 + current_end.month - current_start.month
        )
        avg_monthly = round(period_total / months_in_period, 2)

        # breakdown
        rental_total = round(
            AnalyticsService._sum_rental_spending(db, user_id, current_start, current_end), 2
        ) if include_rental else 0.0
        purchase_total = round(
            AnalyticsService._sum_purchase_spending(db, user_id, current_start, current_end), 2
        ) if include_purchase else 0.0

        # month-over-month change %
        mom_change = 0.0
        if total_prev_month > 0:
            mom_change = round(((total_month - total_prev_month) / total_prev_month) * 100, 2)

        # period comparison
        prev_period_total = _range_total(prev_start, prev_end)
        period_change = 0.0
        if prev_period_total > 0:
            period_change = round(((period_total - prev_period_total) / prev_period_total) * 100, 2)

        # inline trends (reuse the trends helper)
        trends = AnalyticsService.get_personal_cost_trends(db, user_id, period, transaction_type)

        return {
            "total_spent_this_month": total_month,
            "total_spent_this_year": total_year,
            "total_spent_lifetime": total_lifetime,
            "avg_monthly_spending": avg_monthly,
            "breakdown": {
                "rentals": rental_total,
                "purchases": purchase_total,
            },
            "month_over_month_change": mom_change,
            "trends": trends,
            "comparison_with_previous_period": {
                "current": period_total,
                "previous": prev_period_total,
                "change_percent": period_change,
            },
        }

    @staticmethod
    def get_personal_cost_trends(
        db: Session,
        user_id: int,
        period: str = "3m",
        transaction_type: str = "all",
    ) -> list:
        """Monthly trend chart data for the requested period.

        Returns a list of {month, rentals, purchases} dicts.
        """
        from dateutil.relativedelta import relativedelta

        current_start, current_end, _, _ = AnalyticsService._resolve_period_dates(period)

        include_rental = transaction_type in ("rental", "all")
        include_purchase = transaction_type in ("purchase", "all")

        # Build month buckets
        trends = []
        cursor = current_start.replace(day=1)
        while cursor <= current_end:
            m_start = cursor
            m_end = (cursor + relativedelta(months=1)) - timedelta(seconds=1)
            if m_end > current_end:
                m_end = current_end

            rental_val = 0.0
            purchase_val = 0.0
            if include_rental:
                rental_val = round(
                    AnalyticsService._sum_rental_spending(db, user_id, m_start, m_end), 2
                )
            if include_purchase:
                purchase_val = round(
                    AnalyticsService._sum_purchase_spending(db, user_id, m_start, m_end), 2
                )

            trends.append({
                "month": cursor.strftime("%Y-%m"),
                "rentals": rental_val,
                "purchases": purchase_val,
            })
            cursor += relativedelta(months=1)

        return trends

    # ─── Battery Usage Stats (Task 8) ───────────────────────────────

    @staticmethod
    def get_personal_usage_stats(db: Session, user_id: int) -> dict:
        """Comprehensive battery usage statistics for a customer.

        Computes rental counts, durations, peak usage patterns, carbon savings,
        favorite station, usage streaks, and earned badges.
        """
        from app.models.rental import Rental, Purchase
        from app.models.battery import Battery
        from app.models.station import Station
        from app.core.config import settings
        from collections import Counter

        # ── 1. Total rentals & purchases ──────────────────────────
        rentals = db.exec(
            select(Rental).where(Rental.user_id == user_id)
        ).all()

        total_rented = len(rentals)

        total_purchased = db.exec(
            select(func.count(Purchase.id)).where(Purchase.user_id == user_id)
        ).one() or 0

        # ── 2. Duration stats (completed rentals only) ────────────
        completed = [r for r in rentals if r.status == "completed" and r.end_time]
        durations_hours = []
        for r in completed:
            dur = (r.end_time - r.start_time).total_seconds() / 3600
            durations_hours.append(dur)

        avg_duration = round(sum(durations_hours) / len(durations_hours), 2) if durations_hours else 0.0
        longest_duration = round(max(durations_hours), 2) if durations_hours else 0.0

        # ── 3. Most rented battery type ───────────────────────────
        battery_ids = [r.battery_id for r in rentals]
        most_rented_type = None
        if battery_ids:
            batteries = db.exec(
                select(Battery.battery_type).where(Battery.id.in_(battery_ids))
            ).all()
            if batteries:
                type_counts = Counter(batteries)
                most_rented_type = type_counts.most_common(1)[0][0]

        # ── 4. Usage patterns ─────────────────────────────────────
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_counter: Counter = Counter()
        hour_counter: Counter = Counter()

        for r in rentals:
            day_counter[day_names[r.start_time.weekday()]] += 1
            hour_counter[str(r.start_time.hour)] += 1

        # Ensure every day is present
        by_day = {d: day_counter.get(d, 0) for d in day_names}

        peak_day = max(by_day, key=by_day.get) if by_day and any(by_day.values()) else None
        peak_hour = hour_counter.most_common(1)[0][0] if hour_counter else None

        usage_patterns = {
            "by_day_of_week": by_day,
            "by_hour_of_day": dict(hour_counter),
            "peak_usage_day": peak_day,
            "peak_usage_hour": f"{peak_hour}:00" if peak_hour is not None else None,
        }

        # ── 5. Carbon saved ───────────────────────────────────────
        total_hours = sum(durations_hours)
        carbon_saved = round(total_hours * settings.CARBON_FACTOR_KG_PER_HOUR, 2)

        # ── 6. Favorite station ───────────────────────────────────
        station_counter: Counter = Counter(r.start_station_id for r in rentals)
        fav_station = {"id": None, "name": None, "rental_count": 0}
        if station_counter:
            fav_id, fav_count = station_counter.most_common(1)[0]
            station = db.get(Station, fav_id)
            fav_station = {
                "id": fav_id,
                "name": station.name if station else None,
                "rental_count": fav_count,
            }

        # ── 7. Current streak (consecutive days with a rental) ────
        if rentals:
            rental_dates = sorted({r.start_time.date() for r in rentals}, reverse=True)
            streak = 0
            today = datetime.utcnow().date()
            expected = today
            for d in rental_dates:
                if d == expected:
                    streak += 1
                    expected -= timedelta(days=1)
                elif d < expected:
                    # Allow gap: the streak only counts from today backwards
                    break
            current_streak = streak
        else:
            current_streak = 0

        # ── 8. Badges ─────────────────────────────────────────────
        badges = []
        completed_count = len(completed)
        if completed_count >= 1:
            badges.append("first_rental")
        if carbon_saved >= 10:
            badges.append("green_warrior")
        if completed_count >= 10:
            badges.append("regular_user")

        return {
            "total_batteries_rented": total_rented,
            "total_batteries_purchased": total_purchased,
            "avg_rental_duration_hours": avg_duration,
            "longest_rental_hours": longest_duration,
            "most_rented_battery_type": most_rented_type,
            "usage_patterns": usage_patterns,
            "carbon_saved_kg": carbon_saved,
            "favorite_station": fav_station,
            "current_streak_days": current_streak,
            "badges_earned": badges,
        }

