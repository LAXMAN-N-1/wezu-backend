from __future__ import annotations
"""
Dealer Portal Inventory API — All endpoints for the dealer inventory screen.

Endpoints:
  GET    /inventory                          — Paginated battery list with filters
  GET    /inventory/metrics                  — Dashboard KPI cards
  GET    /inventory/health-analytics         — Health distribution & alerts
  GET    /inventory/models                   — Model breakdown with demand
  GET    /inventory/search                   — Advanced search
  GET    /inventory/trends                   — Time-series chart data
  POST   /batteries/{batteryId}/status       — Update single battery status
  POST   /batteries                          — Add new battery
  POST   /batteries/bulk-status              — Bulk status update
  POST   /stock-requests                     — Request stock replenishment
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import datetime

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.schemas.dealer_portal_inventory import (
    BatteryStatusUpdateRequest,
    BatteryCreateRequest,
    BulkStatusUpdateRequest,
    StockRequestCreate,
)
from app.services.dealer_portal_inventory_service import DealerPortalInventoryService

router = APIRouter()

svc = DealerPortalInventoryService


# ──────────────────────────────────────────────────
# Helper: resolve dealer_id from current user
# ──────────────────────────────────────────────────

def _get_dealer_id(db: Session, user_id: int) -> int:
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    return dealer.id


# ══════════════════════════════════════════════════
# 1. GET /inventory — Paginated battery list
# ══════════════════════════════════════════════════

@router.get("/inventory")
def get_dealer_inventory(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    stations: Optional[str] = Query(None, description="Comma-separated station IDs"),
    status: Optional[str] = Query(None, description="Filter: available,reserved,maintenance,rented,charging,retired"),
    healthMin: Optional[int] = Query(None, ge=0, le=100, description="Min health %"),
    healthMax: Optional[int] = Query(None, ge=0, le=100, description="Max health %"),
    modelIds: Optional[str] = Query(None, description="Comma-separated model/catalog IDs"),
    search: Optional[str] = Query(None, description="Search serial, model, notes"),
    sortBy: Optional[str] = Query(None, description="Sort field: serial,health,charge,status"),
    sortOrder: Optional[str] = Query("asc", description="asc or desc"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Fetch all batteries in dealer's stations with pagination, filtering, and sorting.
    Returns battery list, pagination info, and inventory summary.
    """
    dealer_id = _get_dealer_id(db, current_user.id)

    result = svc.get_inventory(
        db=db,
        dealer_id=dealer_id,
        page=page,
        limit=limit,
        stations=stations,
        status=status,
        health_min=healthMin,
        health_max=healthMax,
        model_ids=modelIds,
        search=search,
        sort_by=sortBy,
        sort_order=sortOrder,
    )

    return {
        "success": True,
        "data": result,
        "metadata": {
            "response_time": "auto",
            "api_version": "1.0",
        },
    }


# ══════════════════════════════════════════════════
# 2. GET /inventory/metrics — Dashboard KPIs
# ══════════════════════════════════════════════════

@router.get("/inventory/metrics")
def get_inventory_metrics(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Real-time metrics for the dashboard metric cards.
    Returns total stock, available, reserved, maintenance counts,
    trends, utilization rate, health distribution, and sync info.
    """
    dealer_id = _get_dealer_id(db, current_user.id)
    data = svc.get_metrics(db, dealer_id)

    return {
        "success": True,
        "data": data,
        "metadata": {"response_time": "auto"},
    }


# ══════════════════════════════════════════════════
# 3. GET /inventory/health-analytics
# ══════════════════════════════════════════════════

@router.get("/inventory/health-analytics")
def get_health_analytics(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Detailed health distribution analytics with alerts and recommendations.
    Returns health buckets (excellent/good/fair/poor), average health,
    maintenance alerts, and actionable recommendations.
    """
    dealer_id = _get_dealer_id(db, current_user.id)
    data = svc.get_health_analytics(db, dealer_id)

    return {
        "success": True,
        "data": data,
    }


# ══════════════════════════════════════════════════
# 4. GET /inventory/models
# ══════════════════════════════════════════════════

@router.get("/inventory/models")
def get_inventory_models(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Battery models inventory breakdown with demand statistics.
    Returns per-model inventory counts, health averages, demand trends,
    demand forecasts, and reorder recommendations.
    """
    dealer_id = _get_dealer_id(db, current_user.id)
    data = svc.get_models(db, dealer_id)

    return {
        "success": True,
        "data": data,
    }


# ══════════════════════════════════════════════════
# 5. GET /inventory/search — Advanced search
# ══════════════════════════════════════════════════

@router.get("/inventory/search")
def search_inventory(
    q: Optional[str] = Query(None, description="Search term"),
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    healthMin: Optional[int] = Query(None, ge=0, le=100),
    healthMax: Optional[int] = Query(None, ge=0, le=100),
    stations: Optional[str] = Query(None, description="Comma-separated station IDs"),
    modelIds: Optional[str] = Query(None, description="Comma-separated model IDs"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Advanced search across all batteries in dealer's stations.
    Supports full-text search across serial numbers, model names, and notes.
    """
    dealer_id = _get_dealer_id(db, current_user.id)
    data = svc.search_inventory(
        db=db,
        dealer_id=dealer_id,
        q=q,
        status=status,
        health_min=healthMin,
        health_max=healthMax,
        stations=stations,
        model_ids=modelIds,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": data,
    }


# ══════════════════════════════════════════════════
# 6. GET /inventory/trends — Time-series data
# ══════════════════════════════════════════════════

@router.get("/inventory/trends")
def get_inventory_trends(
    metric: str = Query("stock_levels", description="Metric type"),
    period: int = Query(30, ge=1, le=90, description="Days of data"),
    groupBy: str = Query("daily", description="Grouping: daily, weekly"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Time-series data for inventory charts.
    Returns daily/weekly data points for stock levels over the requested period.
    """
    dealer_id = _get_dealer_id(db, current_user.id)
    data = svc.get_trends(
        db=db,
        dealer_id=dealer_id,
        metric=metric,
        period=period,
        group_by=groupBy,
    )

    return {
        "success": True,
        "data": data,
    }


# ══════════════════════════════════════════════════
# 7. POST /batteries/{batteryId}/status
# ══════════════════════════════════════════════════

@router.post("/batteries/{battery_id}/status")
def update_battery_status(
    battery_id: int,
    body: BatteryStatusUpdateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a single battery's status with reason and optional return date.
    Logs a lifecycle event for audit trail.
    """
    dealer_id = _get_dealer_id(db, current_user.id)

    try:
        data = svc.update_battery_status(
            db=db,
            dealer_id=dealer_id,
            battery_id=battery_id,
            new_status=body.status,
            reason=body.reason,
            estimated_return_date=body.estimated_return_date,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Battery status updated successfully",
        "data": data,
    }


# ══════════════════════════════════════════════════
# 8. POST /batteries — Add new battery
# ══════════════════════════════════════════════════

@router.post("/batteries")
def add_battery(
    body: BatteryCreateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Add a new battery to the dealer's inventory at a specified station.
    Validates ownership and serial number uniqueness.
    """
    dealer_id = _get_dealer_id(db, current_user.id)

    try:
        data = svc.add_battery(
            db=db,
            dealer_id=dealer_id,
            serial_number=body.serial_number,
            station_id=body.station_id,
            model_id=body.model_id,
            purchase_price=body.purchase_price,
            purchase_date=body.purchase_date,
            warranty_expiry=body.warranty_expiry,
            iot_device_id=body.iot_device_id,
            battery_type=body.battery_type,
            notes=body.notes,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Battery added successfully",
        "data": data,
    }


# ══════════════════════════════════════════════════
# 9. POST /batteries/bulk-status — Bulk update
# ══════════════════════════════════════════════════

@router.post("/batteries/bulk-status")
def bulk_update_battery_status(
    body: BulkStatusUpdateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update status for multiple batteries at once.
    Returns per-battery success/failure results.
    """
    dealer_id = _get_dealer_id(db, current_user.id)

    try:
        data = svc.bulk_update_status(
            db=db,
            dealer_id=dealer_id,
            battery_ids=body.battery_ids,
            new_status=body.status,
            reason=body.reason,
            estimated_return_date=body.estimated_return_date,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Bulk status update completed",
        "data": data,
    }


# ══════════════════════════════════════════════════
# 10. POST /stock-requests — Request replenishment
# ══════════════════════════════════════════════════

@router.post("/stock-requests")
def create_stock_request(
    body: StockRequestCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Submit a stock replenishment request to the admin/platform.
    Creates a pending request visible in the admin dashboard.
    """
    dealer_id = _get_dealer_id(db, current_user.id)

    try:
        data = svc.create_stock_request(
            db=db,
            dealer_id=dealer_id,
            quantity=body.quantity,
            model_id=body.model_id,
            model_name=body.model_name,
            delivery_date=body.delivery_date,
            priority=body.priority,
            reason=body.reason,
            notes=body.notes,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Stock request submitted successfully",
        "data": data,
    }
