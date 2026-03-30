from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session
from app.api import deps

from app.models.user import User
from app.services.analytics_service import AnalyticsService
import csv
import io

router = APIRouter()

@router.get("/overview")
def get_platform_overview(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Platform KPIs (active users, total rentals, revenue today)"""
    return AnalyticsService.get_platform_overview(db)

@router.get("/trends")
def get_platform_trends(
    period: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Daily/weekly/monthly trend data for rentals and revenue"""
    return AnalyticsService.get_trends(db, period)

@router.get("/conversion-funnel")
def get_conversion_funnel(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Funnel (installs -> registrations -> first rental)"""
    return AnalyticsService.get_conversion_funnel(db)

@router.get("/user-behavior")
def get_user_behavior(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Aggregated user behavior metrics"""
    return AnalyticsService.get_user_behavior(db)

@router.get("/battery-health-distribution")
def get_battery_health_distribution(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Distribution of all batteries by health % range"""
    return AnalyticsService.get_battery_health_distribution(db)

@router.get("/demand-forecast")
def get_demand_forecast(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: 30-day demand forecast per station"""
    return AnalyticsService.get_demand_forecast_per_station(db)

@router.get("/recent-activity")
def get_recent_activity(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Recent Activities"""
    return AnalyticsService.get_recent_activity(db)

@router.get("/top-stations")
def get_top_stations(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Top Stations Dashboard Endpoint"""
    return AnalyticsService.get_top_stations(db)

@router.get("/revenue/by-region")
def get_revenue_by_region(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Revenue breakdown by city/region"""
    return AnalyticsService.get_revenue_by_region(db)

@router.get("/user-growth")
def get_user_growth_metrics(
    period: str = Query("monthly", enum=["weekly", "monthly"]),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: User acquisition and retention trends"""
    return AnalyticsService.get_user_growth(db, period)

@router.get("/inventory-status")
def get_global_inventory_status(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Health of fleet and hardware utilization summary"""
    return AnalyticsService.get_fleet_inventory_status(db)

@router.get("/fraud-risks")
def get_fraud_risks(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Fraud Risk Summary"""
    return AnalyticsService.get_fraud_risk_summary(db)

@router.get("/suspensions")
def get_suspensions(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Global Suspensions History"""
    return AnalyticsService.get_suspensions_history(db)

@router.get("/invite-links")
def get_invite_links(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
) -> Any:
    """Admin: Invite Link Metrics"""
    return AnalyticsService.get_invite_link_metrics(db)

@router.get("/export")
def export_analytics_report(
    report_type: str = Query(..., enum=["overview", "trends", "forecast", "behavior"]),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
):
    """Admin: Export any analytics report as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    filename = f"analytics_{report_type}.csv"
    
    if report_type == "overview":
        data = AnalyticsService.get_platform_overview(db)
        writer.writerow(["Metric", "Value"])
        for k, v in data.items():
            writer.writerow([k, v])
            
    elif report_type == "trends":
        data = AnalyticsService.get_trends(db)
        if data:
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())
                
    elif report_type == "forecast":
        data = AnalyticsService.get_demand_forecast_per_station(db)
        if data:
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())

    elif report_type == "behavior":
        data = AnalyticsService.get_user_behavior(db)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Avg Session Minutes", data["avg_session_minutes"]])
        writer.writerow(["Peak Hours", ",".join(map(str, data["peak_hours"]))])
        writer.writerow([])
        writer.writerow(["Popular Stations"])
        writer.writerow(["Name", "Rentals"])
        for s in data["popular_stations"]:
            writer.writerow([s["name"], s["rentals"]])

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
