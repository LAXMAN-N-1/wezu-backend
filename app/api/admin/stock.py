from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
import uuid

from app.api.deps import get_db, get_current_active_admin
from app.models.battery import Battery, BatteryStatus, LocationType
from app.models.dealer import DealerProfile
from app.models.dealer_stock_request import DealerStockRequest, StockRequestStatus
from app.models.driver_profile import DriverProfile
from app.models.rental import Rental
from app.models.station import Station
from app.models.station_stock import StationStockConfig, ReorderRequest, StockAlertDismissal
from app.models.warehouse import Warehouse
from app.schemas.station_stock import (
    StockOverviewResponse, StationStockResponse, StationStockConfigResponse,
    StationStockConfigUpdate, ReorderRequestCreate, ReorderRequestResponse,
    StockAlertResponse, StationStockDetailResponse, StockForecastResponse,
    LocationStockResponse, DealerStockRequestResponse,
    DealerStockRequestReview, DealerStockRequestFulfillRequest,
    DealerStockRequestFulfillResponse,
)

router = APIRouter()

def get_station_stock_stats(db: Session, station_id: int):
    batteries = db.exec(select(Battery).where(Battery.station_id == station_id)).all()
    
    total = len(batteries)
    available = sum(1 for b in batteries if b.status == BatteryStatus.AVAILABLE)
    rented = sum(1 for b in batteries if b.status == BatteryStatus.RENTED)
    maintenance = sum(1 for b in batteries if b.status == BatteryStatus.MAINTENANCE)
    
    utilization = (rented / total * 100) if total > 0 else 0.0
    
    config = db.exec(select(StationStockConfig).where(StationStockConfig.station_id == station_id)).first()
    max_capacity = config.max_capacity if config else 50
    reorder_point = config.reorder_point if config else int(max_capacity * 0.1)
    
    is_low_stock = available < reorder_point
    
    return {
        "total": total,
        "available": available,
        "rented": rented,
        "maintenance": maintenance,
        "utilization": utilization,
        "is_low_stock": is_low_stock,
        "config": config,
        "batteries": batteries
    }


def _status_value(value: object) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def _serialize_dealer_stock_request(
    db: Session,
    request_row: DealerStockRequest,
) -> DealerStockRequestResponse:
    dealer = db.get(DealerProfile, request_row.dealer_id)
    return DealerStockRequestResponse(
        id=request_row.id or 0,
        dealer_id=request_row.dealer_id,
        dealer_name=dealer.business_name if dealer else None,
        model_id=request_row.model_id,
        model_name=request_row.model_name,
        quantity=request_row.quantity,
        priority=_status_value(request_row.priority),
        status=_status_value(request_row.status),
        reason=request_row.reason,
        notes=request_row.notes,
        admin_notes=request_row.admin_notes,
        rejected_reason=request_row.rejected_reason,
        delivery_date=request_row.delivery_date,
        created_at=request_row.created_at,
        approved_at=request_row.approved_at,
        fulfilled_at=request_row.fulfilled_at,
        fulfilled_quantity=request_row.fulfilled_quantity,
    )


def _select_dealer_destination_station(db: Session, dealer_id: int) -> Optional[Station]:
    return db.exec(
        select(Station)
        .where(Station.dealer_id == dealer_id)
        .where(Station.is_deleted == False)
        .order_by(Station.created_at.asc())
    ).first()


def _select_fulfillment_batteries(
    db: Session,
    *,
    quantity: int,
    model_id: Optional[int],
    warehouse_id: Optional[int],
) -> list[Battery]:
    statement = (
        select(Battery)
        .where(Battery.location_type == LocationType.WAREHOUSE)
        .where(Battery.status == BatteryStatus.AVAILABLE)
        .order_by(Battery.updated_at.asc(), Battery.id.asc())
    )
    if model_id is not None:
        statement = statement.where(Battery.sku_id == model_id)
    if warehouse_id is not None:
        statement = statement.where(Battery.location_id == warehouse_id)
    return db.exec(statement.limit(quantity)).all()

@router.get("/overview", response_model=StockOverviewResponse)
def get_stock_overview(db: Session = Depends(get_db)):
    """Fleet-wide stock summary"""
    stations_count = db.exec(select(func.count(Station.id))).first() or 0
    total_batteries = db.exec(select(func.count(Battery.id))).first() or 0
    
    total_rented = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.RENTED)).first() or 0
    total_available = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.AVAILABLE)).first() or 0
    total_maintenance = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.MAINTENANCE)).first() or 0
    avg_utilization = (total_rented / total_batteries * 100) if total_batteries > 0 else 0.0
    
    warehouse_count = db.exec(select(func.count(Battery.id)).where(Battery.location_type == LocationType.WAREHOUSE)).first() or 0
    service_count = db.exec(select(func.count(Battery.id)).where(Battery.location_type == LocationType.SERVICE_CENTER)).first() or 0
    
    # Grouped battery stats by station ID
    b_stats = db.exec(
        select(Battery.station_id, Battery.status, func.count(Battery.id))
        .where(Battery.station_id.is_not(None)).group_by(Battery.station_id, Battery.status)
    ).all()
    
    station_avail = {}
    for s_id, status, count in b_stats:
        if s_id not in station_avail: station_avail[s_id] = 0
        if status == BatteryStatus.AVAILABLE:
            station_avail[s_id] += count

    configs = db.exec(select(StationStockConfig)).all()
    config_map = {c.station_id: c.reorder_point if c.reorder_point else int(c.max_capacity * 0.1) for c in configs}

    active_dismissals = {d.station_id for d in db.exec(select(StockAlertDismissal).where(StockAlertDismissal.is_active == True)).all()}

    low_stock_alerts = 0
    stations = db.exec(select(Station)).all()
    for station in stations:
        if station.id:
            avail = station_avail.get(station.id, 0)
            reorder = config_map.get(station.id, 5) # Default 5 (50 * 0.1)
            
            if avail < reorder and station.id not in active_dismissals:
                low_stock_alerts += 1

    return StockOverviewResponse(
        total_batteries=total_batteries,
        total_stations=stations_count,
        avg_utilization=avg_utilization,
        low_stock_alerts=low_stock_alerts,
        warehouse_count=warehouse_count,
        service_count=service_count,
        available_count=total_available,
        rented_count=total_rented,
        maintenance_count=total_maintenance
    )

@router.get("/stations", response_model=List[StationStockResponse])
def get_stations_stock(
    alert_only: bool = False,
    sort_by: str = "utilization", # 'name', 'utilization', 'available'
    db: Session = Depends(get_db)
):
    """List all stations with calculated stock health"""
    # Optimized query using group by to get stats
    stations = db.exec(select(Station)).all()
    results = []
    
    configs = {c.station_id: c for c in db.exec(select(StationStockConfig)).all()}
    counts = db.exec(
        select(Battery.station_id, Battery.status, func.count(Battery.id))
        .where(Battery.station_id.is_not(None))
        .group_by(Battery.station_id, Battery.status)
    ).all()
    
    count_map = {}
    for s_id, status, count in counts:
        if s_id not in count_map: count_map[s_id] = {"AVAILABLE": 0, "RENTED": 0, "MAINTENANCE": 0}
        if status == BatteryStatus.AVAILABLE: count_map[s_id]["AVAILABLE"] = count
        elif status == BatteryStatus.RENTED: count_map[s_id]["RENTED"] = count
        elif status == BatteryStatus.MAINTENANCE: count_map[s_id]["MAINTENANCE"] = count
    
    for station in stations:
        if not station.id: continue
        
        config = configs.get(station.id)
        stat = count_map.get(station.id, {"AVAILABLE": 0, "RENTED": 0, "MAINTENANCE": 0})
        
        available = stat["AVAILABLE"]
        rented = stat["RENTED"]
        maintenance = stat["MAINTENANCE"]
            
        total = available + rented + maintenance
        utilization = (rented / total * 100) if total > 0 else 0.0
        
        reorder_point = config.reorder_point if config else int((config.max_capacity if config else 50) * 0.1)
        is_low_stock = available < reorder_point
        
        if alert_only and not is_low_stock:
            continue
            
        results.append(StationStockResponse(
            station_id=station.id,
            station_name=station.name,
            address=station.address,
            latitude=station.latitude,
            longitude=station.longitude,
            available_count=available,
            rented_count=rented,
            maintenance_count=maintenance,
            total_assigned=total,
            utilization_percentage=utilization,
            is_low_stock=is_low_stock,
            config=config
        ))
        
    if sort_by == "utilization":
        results.sort(key=lambda x: x.utilization_percentage, reverse=True)
    elif sort_by == "available":
        results.sort(key=lambda x: x.available_count)
    else:
        results.sort(key=lambda x: x.station_name)
        
    return results

@router.get("/locations", response_model=List[LocationStockResponse])
def get_locations_stock(db: Session = Depends(get_db)):
    """Returns summaries for non-station locations (Warehouse, Service Center)."""
    location_types = [LocationType.WAREHOUSE, LocationType.SERVICE_CENTER]

    counts = db.exec(
        select(
            Battery.location_type,
            Battery.location_id,
            Battery.status,
            func.count(Battery.id),
        )
        .where(Battery.location_type.in_(location_types))
        .group_by(Battery.location_type, Battery.location_id, Battery.status)
    ).all()

    status_map: dict[tuple[LocationType, Optional[int]], dict[str, int]] = {}
    for location_type, location_id, status, count in counts:
        key = (location_type, location_id)
        if key not in status_map:
            status_map[key] = {"AVAILABLE": 0, "RENTED": 0, "MAINTENANCE": 0}
        if status == BatteryStatus.AVAILABLE:
            status_map[key]["AVAILABLE"] = int(count)
        elif status == BatteryStatus.RENTED:
            status_map[key]["RENTED"] = int(count)
        elif status == BatteryStatus.MAINTENANCE:
            status_map[key]["MAINTENANCE"] = int(count)

    warehouse_ids = {
        location_id
        for location_type, location_id in status_map.keys()
        if location_type == LocationType.WAREHOUSE and location_id is not None
    }
    warehouse_name_map: dict[int, str] = {}
    if warehouse_ids:
        warehouse_rows = db.exec(
            select(Warehouse.id, Warehouse.name).where(Warehouse.id.in_(warehouse_ids))
        ).all()
        warehouse_name_map = {
            int(warehouse_id): warehouse_name
            for warehouse_id, warehouse_name in warehouse_rows
            if warehouse_id is not None and warehouse_name
        }

    results: list[LocationStockResponse] = []
    for (location_type, location_id), stats in sorted(
        status_map.items(),
        key=lambda item: (
            item[0][0].value,
            item[0][1] if item[0][1] is not None else 0,
        ),
    ):
        available = stats["AVAILABLE"]
        rented = stats["RENTED"]
        maintenance = stats["MAINTENANCE"]
        total = available + rented + maintenance
        if total <= 0:
            continue

        if location_type == LocationType.WAREHOUSE:
            if location_id is not None:
                location_name = warehouse_name_map.get(location_id, f"Warehouse #{location_id}")
            else:
                location_name = "Warehouse (Unassigned)"
        elif location_type == LocationType.SERVICE_CENTER:
            location_name = (
                f"Service Center #{location_id}"
                if location_id is not None
                else "Service Center (Unassigned)"
            )
        else:
            location_name = location_type.value.replace("_", " ").title()

        results.append(
            LocationStockResponse(
                location_name=location_name,
                location_type=location_type.value,
                available_count=available,
                rented_count=rented,
                maintenance_count=maintenance,
                total_assigned=total,
                utilization_percentage=(rented / total * 100),
            )
        )

    return results

@router.get("/stations/{station_id}", response_model=StationStockDetailResponse)
def get_station_stock_detail(station_id: int, db: Session = Depends(get_db)):
    """Deep detail for a specific station including demand forecast."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    stats = get_station_stock_stats(db, station_id)
    
    station_resp = StationStockResponse(
        station_id=station.id,
        station_name=station.name,
        address=station.address,
        latitude=station.latitude,
        longitude=station.longitude,
        available_count=stats["available"],
        rented_count=stats["rented"],
        maintenance_count=stats["maintenance"],
        total_assigned=stats["total"],
        utilization_percentage=stats["utilization"],
        is_low_stock=stats["is_low_stock"],
        config=stats["config"]
    )
    
    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)
    rentals_last_30_days = db.exec(
        select(func.count(Rental.id)).where(
            Rental.start_station_id == station_id,
            Rental.start_time >= thirty_days_ago,
        )
    ).one() or 0

    avg_rentals_per_day = round(float(rentals_last_30_days) / 30.0, 2)
    projected_demand = int(round(avg_rentals_per_day * 30))
    
    reorder_qty = stats["config"].reorder_quantity if stats["config"] else 20
    
    stockout_days = None
    if avg_rentals_per_day > 0 and stats["available"] < projected_demand:
        stockout_days = max(0, int(stats["available"] / avg_rentals_per_day))
        
    recommended_date = None
    if stockout_days is not None:
        recommended_date = now + timedelta(days=stockout_days)

    forecast = StockForecastResponse(
        avg_rentals_per_day=avg_rentals_per_day,
        projected_demand_30d=projected_demand,
        recommended_reorder=reorder_qty,
        recommended_date=recommended_date,
        predicted_stockout_days=stockout_days
    )
    
    # Serialize batteries manually to avoid deep circular references in generic dict conversion
    battery_list = [{
        "id": str(b.id),
        "serial_number": b.serial_number,
        "status": b.status,
        "health_percentage": b.health_percentage,
        "type": "Li-ion",
        "updated_at": b.updated_at.isoformat() if hasattr(b, 'updated_at') else None
    } for b in stats["batteries"]]
    
    seven_days_ago = (now - timedelta(days=6)).date()
    rental_rows = db.exec(
        select(func.date(Rental.start_time), func.count(Rental.id))
        .where(
            Rental.start_station_id == station_id,
            Rental.start_time >= datetime.combine(
                seven_days_ago,
                datetime.min.time(),
                tzinfo=UTC,
            ),
        )
        .group_by(func.date(Rental.start_time))
    ).all()
    rental_day_map = {}
    for day, count in rental_rows:
        if isinstance(day, str):
            normalized_day = datetime.fromisoformat(day).date()
        else:
            normalized_day = day
        rental_day_map[normalized_day] = int(count)
    base_capacity = max(1, stats["total"])
    trend = []
    for offset in range(7):
        day = seven_days_ago + timedelta(days=offset)
        daily_rentals = rental_day_map.get(day, 0)
        trend.append(round(min(100.0, (daily_rentals / base_capacity) * 100), 2))

    return StationStockDetailResponse(
        station=station_resp,
        forecast=forecast,
        batteries=battery_list,
        utilization_trend=trend
    )

@router.put("/stations/{station_id}/config", response_model=StationStockConfigResponse)
def update_station_stock_config(
    station_id: int, 
    update_data: StationStockConfigUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_active_admin)
):
    """Update reorder triggers and capacity"""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    config = db.exec(select(StationStockConfig).where(StationStockConfig.station_id == station_id)).first()
    
    if not config:
        config = StationStockConfig(station_id=station_id, updated_by=admin_user.id)
        db.add(config)
        
    data = update_data.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(config, key, value)
        
    config.updated_by = admin_user.id
    config.updated_at = datetime.now(UTC)
    
    # Check if this resolves an existing alert
    if config.reorder_point and update_data.reorder_point:
        stats = get_station_stock_stats(db, station_id)
        if stats["available"] >= config.reorder_point:
            # Dismiss active alerts
            active_dismissals = db.exec(select(StockAlertDismissal).where(
                StockAlertDismissal.station_id == station_id,
                StockAlertDismissal.is_active == True
            )).all()
            for d in active_dismissals:
                d.is_active = False
                db.add(d)

    db.commit()
    db.refresh(config)
    return config

@router.post("/reorder", response_model=ReorderRequestResponse)
def create_reorder_request(
    request_in: ReorderRequestCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_active_admin)
):
    """Create a reorder request for a station (FR-ADMIN-INV-003)"""
    new_request = ReorderRequest(
        station_id=request_in.station_id,
        requested_quantity=request_in.requested_quantity,
        reason=request_in.reason,
        created_by=admin_user.id
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    # Background task would send SMS/Email here
    return new_request


@router.get("/dealer-requests", response_model=List[DealerStockRequestResponse])
def list_dealer_stock_requests(
    status: Optional[str] = Query(default=None),
    dealer_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_active_admin),
):
    statement = select(DealerStockRequest).order_by(DealerStockRequest.created_at.desc())
    if dealer_id is not None:
        statement = statement.where(DealerStockRequest.dealer_id == dealer_id)
    if status:
        normalized = status.strip().lower()
        statement = statement.where(DealerStockRequest.status == normalized)

    rows = db.exec(statement.offset(skip).limit(limit)).all()
    return [_serialize_dealer_stock_request(db, row) for row in rows]


@router.post("/dealer-requests/{request_id}/review", response_model=DealerStockRequestResponse)
def review_dealer_stock_request(
    request_id: int,
    body: DealerStockRequestReview,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_active_admin),
):
    stock_request = db.get(DealerStockRequest, request_id)
    if not stock_request:
        raise HTTPException(status_code=404, detail="Dealer stock request not found")

    current_status = _status_value(stock_request.status)
    if current_status in {"fulfilled", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot review a {current_status} stock request",
        )

    if body.action == "approve":
        stock_request.status = StockRequestStatus.APPROVED
        stock_request.approved_by = admin_user.id
        stock_request.approved_at = datetime.now(UTC)
        stock_request.rejected_reason = None
    else:
        stock_request.status = StockRequestStatus.REJECTED
        stock_request.rejected_reason = (body.rejected_reason or "").strip() or "Rejected by admin"

    if body.admin_notes is not None:
        stock_request.admin_notes = body.admin_notes.strip() or None

    stock_request.updated_at = datetime.now(UTC)
    db.add(stock_request)
    db.commit()
    db.refresh(stock_request)
    return _serialize_dealer_stock_request(db, stock_request)


@router.post("/dealer-requests/{request_id}/fulfill", response_model=DealerStockRequestFulfillResponse)
def fulfill_dealer_stock_request(
    request_id: int,
    body: DealerStockRequestFulfillRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_active_admin),
):
    stock_request = db.get(DealerStockRequest, request_id)
    if not stock_request:
        raise HTTPException(status_code=404, detail="Dealer stock request not found")

    current_status = _status_value(stock_request.status)
    if current_status == "fulfilled":
        raise HTTPException(status_code=409, detail="Dealer stock request is already fulfilled")
    if current_status in {"rejected", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot fulfill a {current_status} stock request",
        )

    if body.warehouse_id is not None and db.get(Warehouse, body.warehouse_id) is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if body.assigned_driver_id is not None:
        driver = db.get(DriverProfile, body.assigned_driver_id)
        if driver is None:
            raise HTTPException(status_code=404, detail="Assigned driver not found")
        if (driver.status or "").strip().lower() in {"inactive", "suspended"}:
            raise HTTPException(status_code=400, detail="Assigned driver is not active")

    requested_qty = body.fulfilled_quantity or stock_request.quantity
    if requested_qty <= 0:
        raise HTTPException(status_code=400, detail="fulfilled_quantity must be greater than zero")

    destination_station = _select_dealer_destination_station(db, stock_request.dealer_id)
    if destination_station is None:
        raise HTTPException(
            status_code=400,
            detail="Dealer has no active station configured for stock fulfillment",
        )

    fulfillment_batteries = _select_fulfillment_batteries(
        db,
        quantity=requested_qty,
        model_id=stock_request.model_id,
        warehouse_id=body.warehouse_id,
    )
    if len(fulfillment_batteries) < requested_qty:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Only {len(fulfillment_batteries)} batteries available in warehouse "
                f"for requested quantity {requested_qty}"
            ),
        )

    dealer = db.get(DealerProfile, stock_request.dealer_id)
    order_note = f"Dealer stock fulfillment for request #{stock_request.id}"
    if body.admin_notes:
        order_note = f"{order_note}. {body.admin_notes.strip()}"

    from app.api.v1.orders import create_order as create_logistics_order
    from app.schemas.order import OrderCreate

    order_payload = OrderCreate(
        units=requested_qty,
        destination=destination_station.address,
        notes=order_note,
        customer_name=dealer.business_name if dealer else f"Dealer {stock_request.dealer_id}",
        customer_phone=dealer.contact_phone if dealer else None,
        priority="urgent" if _status_value(stock_request.priority) == "urgent" else "normal",
        total_value=0.0,
        assigned_battery_ids=[str(row.serial_number) for row in fulfillment_batteries],
        assigned_driver_id=body.assigned_driver_id,
        latitude=destination_station.latitude,
        longitude=destination_station.longitude,
    )

    order_response = create_logistics_order(
        order_data=order_payload,
        current_user=admin_user,
        session=db,
        idempotency_key=None,
    )
    order_id = getattr(order_response.data, "id", None) if order_response else None
    if not order_id:
        raise HTTPException(status_code=500, detail="Failed to create logistics fulfillment order")

    now = datetime.now(UTC)
    if _status_value(stock_request.status) == "pending":
        stock_request.status = StockRequestStatus.APPROVED
        stock_request.approved_by = admin_user.id
        stock_request.approved_at = now

    stock_request.status = StockRequestStatus.FULFILLED
    stock_request.fulfilled_at = now
    stock_request.fulfilled_quantity = requested_qty
    stock_request.updated_at = now
    merged_notes = (stock_request.admin_notes or "").strip()
    fulfillment_note = f"Fulfilled via logistics order {order_id}"
    if body.admin_notes:
        fulfillment_note = f"{fulfillment_note}. {body.admin_notes.strip()}"
    stock_request.admin_notes = f"{merged_notes}\n{fulfillment_note}".strip() if merged_notes else fulfillment_note

    db.add(stock_request)
    db.commit()

    return DealerStockRequestFulfillResponse(
        request_id=stock_request.id or request_id,
        status="fulfilled",
        fulfilled_quantity=requested_qty,
        logistics_order_id=str(order_id),
    )


@router.get("/alerts", response_model=List[StockAlertResponse])
def get_active_stock_alerts(db: Session = Depends(get_db)):
    """Return all active low-stock alerts"""
    b_stats = db.exec(select(Battery.station_id, Battery.status, func.count(Battery.id)).where(Battery.station_id.is_not(None)).group_by(Battery.station_id, Battery.status)).all()
    
    s_stats_map = {}
    for s_id, status, count in b_stats:
        if s_id not in s_stats_map: s_stats_map[s_id] = {"total": 0, "available": 0, "rented": 0, "maintenance": 0}
        s_stats_map[s_id]["total"] += count
        if status == BatteryStatus.AVAILABLE: s_stats_map[s_id]["available"] += count
        elif status == BatteryStatus.RENTED: s_stats_map[s_id]["rented"] += count
        elif status == BatteryStatus.MAINTENANCE: s_stats_map[s_id]["maintenance"] += count
            
    configs = db.exec(select(StationStockConfig)).all()
    config_map = {c.station_id: c for c in configs}
    active_dismissals = {d.station_id for d in db.exec(select(StockAlertDismissal).where(StockAlertDismissal.is_active == True)).all()}

    stations = db.exec(select(Station)).all()
    alerts = []
    
    for station in stations:
        if not station.id: continue
        
        stat = s_stats_map.get(station.id, {"total": 0, "available": 0, "rented": 0})
        utilization = (stat["rented"] / max(stat["total"], 1)) * 100
        config = config_map.get(station.id)
        reorder_point = config.reorder_point if config else int((config.max_capacity if config else 50) * 0.1)
        
        if stat["available"] < reorder_point and station.id not in active_dismissals:
            alerts.append(StockAlertResponse(
                station_id=station.id,
                station_name=station.name,
                current_count=stat["available"],
                capacity=config.max_capacity if config else 50,
                threshold=reorder_point,
                utilization_percentage=utilization
            ))
    return alerts

@router.post("/alerts/{station_id}/dismiss")
def dismiss_stock_alert(
    station_id: int,
    reason: str,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_active_admin)
):
    """Dismiss a low stock alert"""
    dismissal = StockAlertDismissal(
        station_id=station_id,
        reason=reason,
        dismissed_by=admin_user.id
    )
    db.add(dismissal)
    db.commit()
    return {"status": "success", "message": "Alert dismissed"}
