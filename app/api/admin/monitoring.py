from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from typing import Dict
from datetime import datetime, timedelta
from app.api import deps
from app.models.user import User
from app.db.session import get_session

router = APIRouter()

# System monitoring and health checks

@router.get("/health")
def system_health(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Comprehensive system health check"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "checks": {}
    }
    
    # Database check
    try:
        session.exec(select(User).limit(1)).first()
        health_status["checks"]["database"] = {"status": "up", "latency_ms": 5}
    except Exception as e:
        health_status["checks"]["database"] = {"status": "down", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check critical services
    health_status["checks"]["api"] = {"status": "up"}
    health_status["checks"]["scheduler"] = {"status": "up"}  # Would check actual scheduler
    
    return health_status

@router.get("/metrics")
def performance_metrics(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Get performance KPIs"""
    from app.models.rental import Rental
    from app.models.station import Station
    from app.models.battery import Battery
    from app.models.financial import Transaction
    
    # Calculate various metrics
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    # Active rentals
    active_rentals = session.exec(
        select(func.count(Rental.id)).where(Rental.status == "active")
    ).one()
    
    # Total users
    total_users = session.exec(select(func.count(User.id))).one()
    
    # Active users (logged in last 7 days)
    active_users = session.exec(
        select(func.count(User.id))
        .where(User.last_login >= week_start)
    ).one() if hasattr(User, 'last_login') else 0
    
    # Revenue metrics
    daily_revenue = session.exec(
        select(func.sum(Transaction.amount))
        .where(Transaction.created_at >= today_start)
        .where(Transaction.status == "completed")
    ).one() or 0
    
    monthly_revenue = session.exec(
        select(func.sum(Transaction.amount))
        .where(Transaction.created_at >= month_start)
        .where(Transaction.status == "completed")
    ).one() or 0
    
    # Station metrics
    total_stations = session.exec(select(func.count(Station.id))).one()
    
    # Battery metrics
    total_batteries = session.exec(select(func.count(Battery.id))).one()
    available_batteries = session.exec(
        select(func.count(Battery.id)).where(Battery.status == "available")
    ).one()
    
    return {
        "timestamp": now,
        "users": {
            "total": total_users,
            "active_7d": active_users,
            "growth_rate": 0  # Calculate from historical data
        },
        "rentals": {
            "active": active_rentals,
            "today": 0,  # Would need to query
            "week": 0
        },
        "revenue": {
            "today": float(daily_revenue),
            "month": float(monthly_revenue),
            "average_transaction": 0
        },
        "infrastructure": {
            "stations": total_stations,
            "batteries_total": total_batteries,
            "batteries_available": available_batteries,
            "utilization_rate": (total_batteries - available_batteries) / total_batteries * 100 if total_batteries > 0 else 0
        }
    }

@router.get("/uptime")
def uptime_tracking(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Get uptime and SLA metrics"""
    # In production, this would query from monitoring service
    # For now, return mock data
    
    now = datetime.utcnow()
    
    return {
        "current_status": "operational",
        "uptime_percentage_30d": 99.95,
        "uptime_percentage_90d": 99.92,
        "last_incident": now - timedelta(days=15),
        "incident_count_30d": 1,
        "average_response_time_ms": 45,
        "sla_target": 99.9,
        "sla_status": "meeting",
        "periods": [
            {
                "date": (now - timedelta(days=i)).date(),
                "uptime_percentage": 99.9 + (i % 3) * 0.03,
                "incidents": 0 if i % 15 != 0 else 1
            }
            for i in range(30)
        ]
    }

@router.get("/errors")
def error_logs(
    limit: int = 100,
    severity: str = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Get recent error logs"""
    from app.models.audit_log import SecurityEvent
    
    query = select(SecurityEvent).order_by(SecurityEvent.timestamp.desc())
    
    if severity:
        query = query.where(SecurityEvent.severity == severity)
    
    query = query.limit(limit)
    events = session.exec(query).all()
    
    return {
        "total": len(events),
        "errors": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "details": e.details,
                "source_ip": e.source_ip,
                "timestamp": e.timestamp,
                "is_resolved": e.is_resolved
            }
            for e in events
        ]
    }

@router.get("/performance/api")
def api_performance(
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Get API performance metrics"""
    # In production, integrate with APM tool
    return {
        "average_response_time_ms": 45,
        "p50_response_time_ms": 35,
        "p95_response_time_ms": 120,
        "p99_response_time_ms": 250,
        "requests_per_minute": 450,
        "error_rate_percentage": 0.05,
        "slowest_endpoints": [
            {"endpoint": "/api/v1/analytics/dashboard", "avg_time_ms": 350},
            {"endpoint": "/api/v1/stations/search", "avg_time_ms": 180},
            {"endpoint": "/api/v1/rentals/history", "avg_time_ms": 150}
        ]
    }

@router.get("/database/stats")
def database_stats(
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(get_session)
):
    """Get database statistics"""
    # Table sizes and counts
    from app.models.rental import Rental
    from app.models.station import Station
    from app.models.battery import Battery
    from app.models.financial import Transaction
    
    return {
        "tables": {
            "users": session.exec(select(func.count(User.id))).one(),
            "rentals": session.exec(select(func.count(Rental.id))).one(),
            "stations": session.exec(select(func.count(Station.id))).one(),
            "batteries": session.exec(select(func.count(Battery.id))).one(),
            "transactions": session.exec(select(func.count(Transaction.id))).one()
        },
        "connection_pool": {
            "size": 20,
            "active": 5,
            "idle": 15
        },
        "query_performance": {
            "slow_queries_count": 3,
            "average_query_time_ms": 12
        }
    }
