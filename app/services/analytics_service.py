"""
Customer Analytics Service
Personal dashboard and usage statistics
"""
from sqlmodel import Session, select, func
from typing import Dict, List
from datetime import datetime, timedelta
from app.models.rental import Rental
from app.models.financial import Transaction
from app.models.catalog import CatalogOrder
from app.models.station import Station
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Customer analytics and dashboard"""
    
    @staticmethod
    def get_customer_dashboard(user_id: int, session: Session) -> Dict:
        """
        Get comprehensive customer dashboard
        
        Returns:
            Dashboard data with stats, activity, and insights
        """
        now = datetime.utcnow()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Active rentals
        active_rentals = session.exec(
            select(Rental)
            .where(Rental.user_id == user_id)
            .where(Rental.status == "active")
        ).all()
        
        # Total rentals (lifetime)
        total_rentals = session.exec(
            select(func.count(Rental.id))
            .where(Rental.user_id == user_id)
        ).one()
        
        # Total spent (this month)
        month_transactions = session.exec(
            select(func.sum(Transaction.amount))
            .where(Transaction.user_id == user_id)
            .where(Transaction.status == "SUCCESS")
            .where(Transaction.created_at >= this_month_start)
        ).one() or 0
        
        # Total spent (lifetime)
        total_spent = session.exec(
            select(func.sum(Transaction.amount))
            .where(Transaction.user_id == user_id)
            .where(Transaction.status == "SUCCESS")
        ).one() or 0
        
        # Recent orders
        recent_orders = session.exec(
            select(CatalogOrder)
            .where(CatalogOrder.user_id == user_id)
            .order_by(CatalogOrder.created_at.desc())
            .limit(5)
        ).all()
        
        # Favorite stations (most visited)
        favorite_stations = session.exec(
            select(
                Rental.pickup_station_id,
                func.count(Rental.id).label('visit_count')
            )
            .where(Rental.user_id == user_id)
            .group_by(Rental.pickup_station_id)
            .order_by(func.count(Rental.id).desc())
            .limit(3)
        ).all()
        
        favorite_station_details = []
        for station_id, count in favorite_stations:
            station = session.get(Station, station_id)
            if station:
                favorite_station_details.append({
                    'station_id': station.id,
                    'name': station.name,
                    'visit_count': count
                })
        
        return {
            'active_rentals_count': len(active_rentals),
            'total_rentals_lifetime': total_rentals,
            'spent_this_month': float(month_transactions),
            'total_spent_lifetime': float(total_spent),
            'recent_orders_count': len(recent_orders),
            'favorite_stations': favorite_station_details,
            'membership_tier': AnalyticsService._calculate_tier(total_rentals)
        }
    
    @staticmethod
    def get_rental_history_stats(user_id: int, session: Session) -> Dict:
        """Get rental history statistics"""
        rentals = session.exec(
            select(Rental)
            .where(Rental.user_id == user_id)
            .where(Rental.status.in_(["completed", "active"]))
        ).all()
        
        if not rentals:
            return {
                'total_rentals': 0,
                'total_hours': 0,
                'average_duration_hours': 0,
                'total_cost': 0,
                'average_cost': 0
            }
        
        total_hours = sum(r.duration_hours or 0 for r in rentals)
        total_cost = sum(r.total_cost or 0 for r in rentals)
        
        return {
            'total_rentals': len(rentals),
            'total_hours': round(total_hours, 2),
            'average_duration_hours': round(total_hours / len(rentals), 2),
            'total_cost': round(total_cost, 2),
            'average_cost': round(total_cost / len(rentals), 2)
        }
    
    @staticmethod
    def get_cost_analytics(user_id: int, months: int, session: Session) -> Dict:
        """Get cost analytics for specified months"""
        start_date = datetime.utcnow() - timedelta(days=months * 30)
        
        # Monthly breakdown
        transactions = session.exec(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.status == "SUCCESS")
            .where(Transaction.created_at >= start_date)
            .order_by(Transaction.created_at)
        ).all()
        
        # Group by month
        monthly_data = {}
        for txn in transactions:
            month_key = txn.created_at.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'rental': 0,
                    'purchase': 0,
                    'late_fee': 0,
                    'total': 0
                }
            
            if txn.transaction_type == "RENTAL":
                monthly_data[month_key]['rental'] += txn.amount
            elif txn.transaction_type == "PURCHASE":
                monthly_data[month_key]['purchase'] += txn.amount
            elif txn.transaction_type == "LATE_FEE":
                monthly_data[month_key]['late_fee'] += txn.amount
            
            monthly_data[month_key]['total'] += txn.amount
        
        # Convert to list
        monthly_breakdown = [
            {
                'month': month,
                'rental': round(data['rental'], 2),
                'purchase': round(data['purchase'], 2),
                'late_fee': round(data['late_fee'], 2),
                'total': round(data['total'], 2)
            }
            for month, data in sorted(monthly_data.items())
        ]
        
        total_spent = sum(data['total'] for data in monthly_data.values())
        
        return {
            'period_months': months,
            'total_spent': round(total_spent, 2),
            'average_monthly': round(total_spent / months, 2) if months > 0 else 0,
            'monthly_breakdown': monthly_breakdown
        }
    
    @staticmethod
    def get_usage_patterns(user_id: int, session: Session) -> Dict:
        """Analyze usage patterns"""
        rentals = session.exec(
            select(Rental)
            .where(Rental.user_id == user_id)
            .where(Rental.status == "completed")
        ).all()
        
        if not rentals:
            return {
                'most_active_day': None,
                'most_active_hour': None,
                'average_rental_duration': 0
            }
        
        # Day of week analysis
        day_counts = {}
        hour_counts = {}
        
        for rental in rentals:
            day = rental.start_time.strftime('%A')
            hour = rental.start_time.hour
            
            day_counts[day] = day_counts.get(day, 0) + 1
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        most_active_day = max(day_counts, key=day_counts.get) if day_counts else None
        most_active_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None
        
        avg_duration = sum(r.duration_hours or 0 for r in rentals) / len(rentals)
        
        return {
            'most_active_day': most_active_day,
            'most_active_hour': most_active_hour,
            'average_rental_duration': round(avg_duration, 2),
            'total_completed_rentals': len(rentals)
        }
    
    @staticmethod
    def _calculate_tier(total_rentals: int) -> str:
        """Calculate membership tier based on rentals"""
        if total_rentals >= 50:
            return "PLATINUM"
        elif total_rentals >= 20:
            return "GOLD"
        elif total_rentals >= 5:
            return "SILVER"
        else:
            return "BRONZE"
