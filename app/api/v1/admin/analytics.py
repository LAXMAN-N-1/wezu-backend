from threading import Lock
from time import monotonic
from typing import Any, Callable, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session
from app.api import deps
from app.core.config import settings

from app.models.user import User
from app.services.analytics_service import AnalyticsService
import csv
import io
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
_analytics_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
_analytics_cache_lock = Lock()


def _prune_expired_cache(now: float) -> None:
    expired = [key for key, (expires_at, _) in _analytics_cache.items() if expires_at <= now]
    for key in expired:
        _analytics_cache.pop(key, None)


def _analytics_response(
    endpoint: str,
    call: Callable[[], Any],
    *cache_parts: Any,
    ttl_seconds: Optional[int] = None,
) -> Any:
    ttl = settings.ANALYTICS_CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    cache_key = (endpoint,) + tuple(cache_parts)

    if ttl > 0:
        now = monotonic()
        with _analytics_cache_lock:
            cached = _analytics_cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]
            _prune_expired_cache(now)

    try:
        result = call()
    except Exception:
        logger.exception("admin.analytics.failed", extra={"endpoint": endpoint})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="analytics_unavailable",
        )

    if ttl > 0:
        with _analytics_cache_lock:
            _analytics_cache[cache_key] = (monotonic() + ttl, result)

    return result

@router.get("/overview")
def get_platform_overview(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Platform KPIs (active users, total rentals, revenue today)"""
    return _analytics_response(
        "overview",
        lambda: AnalyticsService.get_platform_overview(db, period),
        period,
    )

@router.get("/trends")
def get_platform_trends(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Daily/weekly/monthly trend data for rentals and revenue"""
    return _analytics_response(
        "trends",
        lambda: AnalyticsService.get_trends(db, period),
        period,
    )

@router.get("/conversion-funnel")
def get_conversion_funnel(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Funnel (installs -> registrations -> first rental)"""
    return _analytics_response(
        "conversion-funnel",
        lambda: AnalyticsService.get_conversion_funnel(db),
    )

@router.get("/user-behavior")
def get_user_behavior(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Aggregated user behavior metrics"""
    return _analytics_response(
        "user-behavior",
        lambda: AnalyticsService.get_user_behavior(db),
    )

@router.get("/battery-health-distribution")
def get_battery_health_distribution(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Distribution of all batteries by health % range"""
    return _analytics_response(
        "battery-health-distribution",
        lambda: AnalyticsService.get_battery_health_distribution(db),
    )

@router.get("/demand-forecast")
def get_demand_forecast(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: 7-day demand forecast with actuals"""
    return _analytics_response(
        "demand-forecast",
        lambda: AnalyticsService.get_demand_forecast_per_station(db),
    )

@router.get("/recent-activity")
def get_recent_activity(
    type: Optional[str] = Query(None, description="Filter by activity type"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Recent Activities"""
    return _analytics_response(
        "recent-activity",
        lambda: AnalyticsService.get_recent_activity(db, type),
        type or "all",
    )

@router.get("/revenue/by-station")
def get_revenue_by_station(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue distribution by station"""
    return _analytics_response(
        "revenue-by-station",
        lambda: AnalyticsService.get_revenue_by_station_detailed(db, period),
        period,
    )

@router.get("/revenue/by-battery-type")
def get_revenue_by_battery_type(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue split by battery chemistry/model"""
    return _analytics_response(
        "revenue-by-battery-type",
        lambda: AnalyticsService.get_revenue_by_battery_type(db, period),
        period,
    )

@router.get("/top-stations")
def get_top_stations(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Top Stations Dashboard Endpoint"""
    return _analytics_response(
        "top-stations",
        lambda: AnalyticsService.get_top_stations(db),
    )

@router.get("/revenue/by-region")
def get_revenue_by_region(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue breakdown by city/region"""
    return _analytics_response(
        "revenue-by-region",
        lambda: AnalyticsService.get_revenue_by_region(db),
    )

@router.get("/user-growth")
def get_user_growth_metrics(
    period: str = Query("monthly", enum=["weekly", "monthly"]),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: User acquisition and retention trends"""
    return _analytics_response(
        "user-growth",
        lambda: AnalyticsService.get_user_growth(db, period),
        period,
    )

@router.get("/inventory-status")
def get_global_inventory_status(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Health of fleet and hardware utilization summary"""
    return _analytics_response(
        "inventory-status",
        lambda: AnalyticsService.get_fleet_inventory_status(db),
    )

@router.get("/export")
def export_analytics_report(
    report_type: str = Query(..., enum=["overview", "trends", "forecast", "behavior"]),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    """Admin: Export any analytics report as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    filename = f"analytics_{report_type}.csv"
    
    if report_type == "overview":
        data = _analytics_response(
            "overview",
            lambda: AnalyticsService.get_platform_overview(db, "30d"),
            "30d",
        )
        writer.writerow(["Metric", "Value"])
        for k, v in data.items():
            writer.writerow([k, v.get("value", v)])
            
    elif report_type == "trends":
        data = _analytics_response(
            "trends",
            lambda: AnalyticsService.get_trends(db, "30d"),
            "30d",
        ).get("data", [])
        if data:
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())
                
    elif report_type == "forecast":
        data = _analytics_response(
            "demand-forecast",
            lambda: AnalyticsService.get_demand_forecast_per_station(db),
        )
        forecast = data.get("forecast", []) if isinstance(data, dict) else data
        if forecast:
            writer.writerow(forecast[0].keys())
            for row in forecast:
                writer.writerow(row.values())

    elif report_type == "behavior":
        data = _analytics_response(
            "user-behavior",
            lambda: AnalyticsService.get_user_behavior(db),
        )
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Avg Session Minutes", data.get("avg_session_duration", 0)])
        writer.writerow(["Avg Rentals/User", data.get("avg_rentals_per_user", 0)])
        writer.writerow(["Peak Hours", ",".join(map(str, data.get("peak_hours", {}).keys()))])

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
