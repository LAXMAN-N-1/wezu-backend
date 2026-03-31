from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from app.api import deps
from app.models.user import User

router = APIRouter()

@router.get("/overview")
def get_analytics_overview(current_user: User = Depends(deps.get_current_active_admin)):
    return {
        "revenue": {"total": 125000, "growth": 12.5},
        "active_users": {"total": 850, "growth": 8.1},
        "battery_swaps": {"total": 3200, "growth": 5.2},
        "fleet_utilization": {"percentage": 78.4, "growth": -2.1}
    }

@router.get("/trends")
def get_analytics_trends(period: str = "daily", current_user: User = Depends(deps.get_current_active_admin)):
    return {
        "dates": ["2026-03-24", "2026-03-25", "2026-03-26", "2026-03-27", "2026-03-28", "2026-03-29", "2026-03-30"],
        "revenue": [12000, 15000, 13000, 18000, 21000, 19000, 22000],
        "swaps": [450, 520, 480, 610, 720, 680, 750]
    }

@router.get("/battery-health-distribution")
def get_battery_health_distribution(current_user: User = Depends(deps.get_current_active_admin)):
    return [
        {"status": "Excellent", "count": 1200, "color": "#10B981"},
        {"status": "Good", "count": 800, "color": "#3B82F6"},
        {"status": "Fair", "count": 350, "color": "#F59E0B"},
        {"status": "Critical", "count": 50, "color": "#EF4444"}
    ]

@router.get("/revenue/by-region")
def get_revenue_by_region(current_user: User = Depends(deps.get_current_active_admin)):
    return [
        {"region": "North", "value": 45000},
        {"region": "South", "value": 35000},
        {"region": "East", "value": 25000},
        {"region": "West", "value": 20000}
    ]

@router.get("/revenue/by-station")
def get_revenue_by_station(period: str = "30d", current_user: User = Depends(deps.get_current_active_admin)):
    return [
        {"station": "Station Alpha", "value": 15000},
        {"station": "Station Beta", "value": 12000},
        {"station": "Station Gamma", "value": 11000},
        {"station": "Station Delta", "value": 9000},
        {"station": "Station Epsilon", "value": 8500}
    ]

@router.get("/recent-activity")
def get_recent_activity(current_user: User = Depends(deps.get_current_active_admin)):
    return [
        {"id": 1, "type": "swap", "description": "New battery swap at Station Alpha", "timestamp": "2026-03-30T05:00:00"},
        {"id": 2, "type": "user", "description": "New user registered: John Doe", "timestamp": "2026-03-30T04:45:00"},
        {"id": 3, "type": "alert", "description": "Low inventory alert at Station Beta", "timestamp": "2026-03-30T04:30:00"}
    ]

@router.get("/top-stations")
def get_top_stations(current_user: User = Depends(deps.get_current_active_admin)):
    return [
        {"id": 1, "name": "Station Alpha", "swaps": 120, "revenue": 5600, "status": "active"},
        {"id": 2, "name": "Station Beta", "swaps": 98, "revenue": 4800, "status": "active"},
        {"id": 3, "name": "Station Gamma", "swaps": 85, "revenue": 4200, "status": "warning"}
    ]

@router.get("/conversion-funnel")
def get_conversion_funnel(current_user: User = Depends(deps.get_current_active_admin)):
    return [
        {"stage": "Visitors", "value": 10000},
        {"stage": "Signups", "value": 2500},
        {"stage": "KYC Approved", "value": 1800},
        {"stage": "First Swap", "value": 1200}
    ]

@router.get("/demand-forecast")
def get_demand_forecast(current_user: User = Depends(deps.get_current_active_admin)):
    return {
        "dates": ["2026-03-31", "2026-04-01", "2026-04-02", "2026-04-03"],
        "forecast": [800, 850, 920, 880],
        "lower_bound": [750, 800, 850, 820],
        "upper_bound": [850, 900, 990, 940]
    }

@router.get("/inventory-status")
def get_inventory_status(current_user: User = Depends(deps.get_current_active_admin)):
    return {
        "available": 450,
        "in_transit": 85,
        "maintenance": 42,
        "dispatched": 1200
    }
