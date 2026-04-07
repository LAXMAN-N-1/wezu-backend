from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.api import deps
from app.services.admin_analytics_service import AdminAnalyticsService
from app.utils.runtime_cache import cached_call
from app.core.config import settings
from typing import Any

router = APIRouter()

_NS = "admin-analytics"


@router.get("/overview")
def get_overview(db: Session = Depends(deps.get_db)) -> Any:
    """Get high-level dashboard KPI metrics."""
    return cached_call(_NS, "overview", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_overview(db))


@router.get("/trends")
def get_trends(
    db: Session = Depends(deps.get_db),
    period: str = Query("daily", enum=["daily", "weekly", "monthly"]),
) -> Any:
    """Get time-series trend data."""
    return cached_call(_NS, "trends", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_trends(db, period=period))


@router.get("/battery-health-distribution")
def get_battery_health_distribution(db: Session = Depends(deps.get_db)) -> Any:
    """Battery health bucket distribution."""
    return cached_call(_NS, "battery-health-distribution", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_battery_health_distribution(db))


@router.get("/revenue/by-region")
def get_revenue_by_region(
    db: Session = Depends(deps.get_db),
    period: str = Query("30d", enum=["30d", "90d"]),
) -> Any:
    """Revenue aggregated by city/region from real rental data."""
    return cached_call(_NS, "revenue-by-region", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_revenue_by_region(db, period=period))


@router.get("/revenue/by-station")
def get_revenue_by_station(
    db: Session = Depends(deps.get_db),
    period: str = Query("30d", enum=["30d", "90d"]),
) -> Any:
    """Revenue aggregated per station from real rental data."""
    return cached_call(_NS, "revenue-by-station", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_revenue_by_station(db, period=period))


@router.get("/revenue/by-battery-type")
def get_revenue_by_battery_type(
    db: Session = Depends(deps.get_db),
    period: str = Query("30d", enum=["30d", "90d"]),
) -> Any:
    """Revenue aggregated by battery model from real rental data."""
    return cached_call(_NS, "revenue-by-battery-type", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_revenue_by_battery_type(db, period=period))


@router.get("/conversion-funnel")
def get_conversion_funnel(db: Session = Depends(deps.get_db)) -> Any:
    """Real user conversion funnel: Registered → Active → Rented → Completed."""
    return cached_call(_NS, "conversion-funnel", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_conversion_funnel(db))


@router.get("/recent-activity")
def get_recent_activity(db: Session = Depends(deps.get_db)) -> Any:
    """Latest events from DB (new users + recent rentals)."""
    return cached_call(_NS, "recent-activity", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_recent_activity(db))


@router.get("/top-stations")
def get_top_stations(db: Session = Depends(deps.get_db)) -> Any:
    """Top performing stations by rental revenue (last 30 days)."""
    return cached_call(_NS, "top-stations", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_top_stations(db))


@router.get("/user-behavior")
def get_user_behavior(db: Session = Depends(deps.get_db)) -> Any:
    """User rental behavior metrics: duration, frequency, peak hours."""
    return cached_call(_NS, "user-behavior", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_user_behavior(db))


@router.get("/user-growth")
def get_user_growth(
    db: Session = Depends(deps.get_db),
    period: str = Query("monthly", enum=["monthly", "weekly"]),
) -> Any:
    """User growth trend from real registration timestamps."""
    return cached_call(_NS, "user-growth", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_user_growth(db, period=period))


@router.get("/inventory-status")
def get_inventory_status(db: Session = Depends(deps.get_db)) -> Any:
    """Live battery inventory by status and model."""
    return cached_call(_NS, "inventory-status", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_inventory_status(db))


@router.get("/demand-forecast")
def get_demand_forecast(db: Session = Depends(deps.get_db)) -> Any:
    """7-day demand forecast based on historical weekday averages."""
    return cached_call(_NS, "demand-forecast", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
                       call=lambda: AdminAnalyticsService.get_demand_forecast(db))


@router.get("/export")
def export_analytics_report(
    db: Session = Depends(deps.get_db),
    report_type: str = Query("overview", enum=["overview", "trends", "stations", "batteries"]),
) -> Any:
    """Export analytics data as CSV."""
    from fastapi.responses import StreamingResponse
    import io
    
    csv_string = AdminAnalyticsService.export_report(db, report_type=report_type)
    
    # Create a stream from the string
    stream = io.StringIO(csv_string)
    
    # Return as a downloadable file
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=analytics_{report_type}_report.csv"
    return response
