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
