from typing import Any, Callable, Dict, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session
from app.api import deps

from app.models.user import User
from app.services.analytics_service import AnalyticsService
import csv
import io
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_analytics(call: Callable[[], Any], fallback: Any, endpoint: str) -> Any:
    try:
        return call()
    except Exception:
        logger.exception("Admin analytics endpoint failed: %s", endpoint)
        return fallback


def _overview_fallback() -> Dict[str, Any]:
    return {
        "total_revenue": {"label": "Total Revenue", "value": 0, "change_percent": 0.0, "sparkline": []},
        "active_rentals": {"label": "Active Rentals", "value": 0, "change_percent": 0.0, "sparkline": []},
        "total_users": {"label": "Total Users", "value": 0, "change_percent": 0.0, "sparkline": []},
        "fleet_utilization": {"label": "Fleet Utilization", "value": 0.0, "change_percent": 0.0, "sparkline": []},
        "active_stations": {"label": "Active Stations", "value": 0, "change_percent": 0.0},
        "active_dealers": {"label": "Active Dealers", "value": 0, "change_percent": 0.0},
        "avg_battery_health": {"label": "Avg. Battery Health", "value": 0.0, "change_percent": 0.0},
        "open_tickets": {"label": "Open Tickets", "value": 0, "change_percent": 0.0},
        "revenue_per_rental": {"label": "Revenue per Rental", "value": 0.0, "change_percent": 0.0},
        "avg_session_duration": {"label": "Avg. Session", "value": 0.0, "change_percent": 0.0},
    }


def _trends_fallback(period: str) -> Dict[str, Any]:
    return {"period": period, "data": []}

@router.get("/overview")
def get_platform_overview(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Platform KPIs (active users, total rentals, revenue today)"""
    return _safe_analytics(
        lambda: AnalyticsService.get_platform_overview(db, period),
        _overview_fallback(),
        "overview",
    )

@router.get("/trends")
def get_platform_trends(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Daily/weekly/monthly trend data for rentals and revenue"""
    return _safe_analytics(
        lambda: AnalyticsService.get_trends(db, period),
        _trends_fallback(period),
        "trends",
    )

@router.get("/conversion-funnel")
def get_conversion_funnel(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Funnel (installs -> registrations -> first rental)"""
    return _safe_analytics(
        lambda: AnalyticsService.get_conversion_funnel(db),
        {"stages": []},
        "conversion-funnel",
    )

@router.get("/user-behavior")
def get_user_behavior(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Aggregated user behavior metrics"""
    return _safe_analytics(
        lambda: AnalyticsService.get_user_behavior(db),
        {
            "avg_session_duration": 0.0,
            "avg_rentals_per_user": 0.0,
            "peak_hours": {},
            "heatmap": [],
            "session_histogram": [],
            "cohort_breakdown": {},
        },
        "user-behavior",
    )

@router.get("/battery-health-distribution")
def get_battery_health_distribution(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Distribution of all batteries by health % range"""
    return _safe_analytics(
        lambda: AnalyticsService.get_battery_health_distribution(db),
        {"total": 0, "previous_total": 0, "distribution": [], "previous_distribution": []},
        "battery-health-distribution",
    )

@router.get("/demand-forecast")
def get_demand_forecast(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: 7-day demand forecast with actuals"""
    return _safe_analytics(
        lambda: AnalyticsService.get_demand_forecast_per_station(db),
        {"forecast": []},
        "demand-forecast",
    )

@router.get("/recent-activity")
def get_recent_activity(
    type: Optional[str] = Query(None, description="Filter by activity type"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Recent Activities"""
    return _safe_analytics(
        lambda: AnalyticsService.get_recent_activity(db, type),
        {"activities": []},
        "recent-activity",
    )

@router.get("/revenue/by-station")
def get_revenue_by_station(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue distribution by station"""
    return _safe_analytics(
        lambda: AnalyticsService.get_revenue_by_station_detailed(db, period),
        {"total_revenue": 0.0, "stations": []},
        "revenue-by-station",
    )

@router.get("/revenue/by-battery-type")
def get_revenue_by_battery_type(
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue split by battery chemistry/model"""
    return _safe_analytics(
        lambda: AnalyticsService.get_revenue_by_battery_type(db, period),
        {"types": [], "station_mix": []},
        "revenue-by-battery-type",
    )

@router.get("/top-stations")
def get_top_stations(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Top Stations Dashboard Endpoint"""
    return _safe_analytics(
        lambda: AnalyticsService.get_top_stations(db),
        {"stations": []},
        "top-stations",
    )

@router.get("/revenue/by-region")
def get_revenue_by_region(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue breakdown by city/region"""
    return _safe_analytics(
        lambda: AnalyticsService.get_revenue_by_region(db),
        [],
        "revenue-by-region",
    )

@router.get("/user-growth")
def get_user_growth_metrics(
    period: str = Query("monthly", enum=["weekly", "monthly"]),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: User acquisition and retention trends"""
    return _safe_analytics(
        lambda: AnalyticsService.get_user_growth(db, period),
        [],
        "user-growth",
    )

@router.get("/inventory-status")
def get_global_inventory_status(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Health of fleet and hardware utilization summary"""
    return _safe_analytics(
        lambda: AnalyticsService.get_fleet_inventory_status(db),
        {
            "total_batteries": 0,
            "total_available": 0,
            "inventory": [],
            "status_breakdown": {"rented": 0, "charging": 0, "available": 0},
            "utilization_rate": 0,
        },
        "inventory-status",
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
        data = _safe_analytics(
            lambda: AnalyticsService.get_platform_overview(db, "30d"),
            _overview_fallback(),
            "export-overview",
        )
        writer.writerow(["Metric", "Value"])
        for k, v in data.items():
            writer.writerow([k, v.get("value", v)])
            
    elif report_type == "trends":
        data = _safe_analytics(
            lambda: AnalyticsService.get_trends(db, "30d"),
            _trends_fallback("30d"),
            "export-trends",
        ).get("data", [])
        if data:
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())
                
    elif report_type == "forecast":
        data = _safe_analytics(
            lambda: AnalyticsService.get_demand_forecast_per_station(db),
            {"forecast": []},
            "export-forecast",
        )
        forecast = data.get("forecast", []) if isinstance(data, dict) else data
        if forecast:
            writer.writerow(forecast[0].keys())
            for row in forecast:
                writer.writerow(row.values())

    elif report_type == "behavior":
        data = _safe_analytics(
            lambda: AnalyticsService.get_user_behavior(db),
            {
                "avg_session_duration": 0.0,
                "avg_rentals_per_user": 0.0,
                "peak_hours": {},
            },
            "export-behavior",
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
