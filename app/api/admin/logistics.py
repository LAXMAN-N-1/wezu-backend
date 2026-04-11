from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc
from typing import List, Optional
from datetime import datetime, UTC
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.logistics import DeliveryOrder, DeliveryStatus, DeliveryType
from app.models.driver_profile import DriverProfile
from app.models.delivery_route import DeliveryRoute, RouteStop
from app.models.return_request import ReturnRequest

router = APIRouter()

# ─── DELIVERY ORDERS ──────────────────────────────────────────────────────────

@router.get("/orders")
def list_delivery_orders(
    skip: int = 0, limit: int = 50,
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    statement = select(DeliveryOrder)
    if status:
        statement = statement.where(DeliveryOrder.status == status)
    if order_type:
        statement = statement.where(DeliveryOrder.order_type == order_type)

    total = db.exec(select(func.count(DeliveryOrder.id))).one()
    orders = db.exec(statement.offset(skip).limit(limit).order_by(desc(DeliveryOrder.created_at))).all()

    driver_ids = {o.assigned_driver_id for o in orders if o.assigned_driver_id}
    driver_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(driver_ids))).all()} if driver_ids else {}

    result = []
    for o in orders:
        driver_name = "Unassigned"
        if o.assigned_driver_id:
            driver_user = driver_map.get(o.assigned_driver_id)
            driver_name = driver_user.full_name if driver_user else "Unknown"
        result.append({
            "id": o.id,
            "order_type": o.order_type.value if hasattr(o.order_type, 'value') else str(o.order_type),
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
            "origin_address": o.origin_address,
            "destination_address": o.destination_address,
            "assigned_driver_id": o.assigned_driver_id,
            "driver_name": driver_name,
            "scheduled_at": o.scheduled_at.isoformat() if o.scheduled_at else None,
            "started_at": o.started_at.isoformat() if o.started_at else None,
            "completed_at": o.completed_at.isoformat() if o.completed_at else None,
            "otp_verified": o.otp_verified,
            "created_at": o.created_at.isoformat(),
        })
    return {"orders": result, "total_count": total}

@router.get("/orders/stats")
def get_order_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    total = db.exec(select(func.count(DeliveryOrder.id))).one()
    pending = db.exec(select(func.count(DeliveryOrder.id)).where(DeliveryOrder.status == DeliveryStatus.PENDING)).one()
    in_transit = db.exec(select(func.count(DeliveryOrder.id)).where(DeliveryOrder.status == DeliveryStatus.IN_TRANSIT)).one()
    delivered = db.exec(select(func.count(DeliveryOrder.id)).where(DeliveryOrder.status == DeliveryStatus.DELIVERED)).one()
    failed = db.exec(select(func.count(DeliveryOrder.id)).where(DeliveryOrder.status == DeliveryStatus.FAILED)).one()

    return {
        "total_orders": total,
        "pending": pending,
        "in_transit": in_transit,
        "delivered": delivered,
        "failed": failed,
    }

@router.post("/orders")
def create_delivery_order(
    order_type: str,
    origin_address: str,
    destination_address: str,
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
    dest_lat: Optional[float] = None,
    dest_lng: Optional[float] = None,
    driver_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    order = DeliveryOrder(
        order_type=order_type,
        origin_address=origin_address,
        destination_address=destination_address,
        origin_lat=origin_lat, origin_lng=origin_lng,
        destination_lat=dest_lat, destination_lng=dest_lng,
        assigned_driver_id=driver_id,
        status=DeliveryStatus.ASSIGNED if driver_id else DeliveryStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@router.put("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    order = db.get(DeliveryOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = new_status
    if new_status == "in_transit":
        order.started_at = datetime.now(UTC)
    elif new_status == "delivered":
        order.completed_at = datetime.now(UTC)
    order.updated_at = datetime.now(UTC)
    db.add(order)
    db.commit()
    return {"status": "success"}


# ─── DRIVERS ──────────────────────────────────────────────────────────────────

@router.get("/drivers")
def list_drivers(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    drivers = db.exec(select(DriverProfile)).all()
    user_ids = {d.user_id for d in drivers if d.user_id}
    user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    result = []
    for d in drivers:
        user = user_map.get(d.user_id)
        result.append({
            "id": d.id,
            "user_id": d.user_id,
            "name": user.full_name if user else "Unknown",
            "phone": user.phone_number if user else "",
            "license_number": d.license_number,
            "vehicle_type": d.vehicle_type,
            "vehicle_plate": d.vehicle_plate,
            "is_online": d.is_online,
            "current_latitude": d.current_latitude,
            "current_longitude": d.current_longitude,
            "rating": d.rating,
            "total_deliveries": d.total_deliveries,
            "on_time_deliveries": d.on_time_deliveries,
            "created_at": d.created_at.isoformat(),
        })
    return result

@router.get("/drivers/stats")
def get_driver_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    total = db.exec(select(func.count(DriverProfile.id))).one()
    online = db.exec(select(func.count(DriverProfile.id)).where(DriverProfile.is_online == True)).one()
    avg_rating = db.exec(select(func.coalesce(func.avg(DriverProfile.rating), 0))).one()
    total_deliveries = db.exec(select(func.coalesce(func.sum(DriverProfile.total_deliveries), 0))).one()

    return {
        "total_drivers": total,
        "online_drivers": online,
        "offline_drivers": total - online,
        "avg_rating": round(float(avg_rating), 1),
        "total_deliveries": total_deliveries,
    }


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@router.get("/routes")
def list_routes(
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    statement = select(DeliveryRoute)
    if status:
        statement = statement.where(DeliveryRoute.status == status)
    routes = db.exec(statement.order_by(desc(DeliveryRoute.created_at))).all()

    driver_profile_ids = {r.driver_id for r in routes if r.driver_id}
    driver_profiles = db.exec(select(DriverProfile).where(DriverProfile.id.in_(driver_profile_ids))).all() if driver_profile_ids else []
    dp_user_map = {dp.id: dp.user_id for dp in driver_profiles}

    d_user_ids = {uid for uid in dp_user_map.values() if uid}
    driver_user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(d_user_ids))).all()} if d_user_ids else {}
    
    route_ids = [r.id for r in routes]
    all_stops = db.exec(select(RouteStop).where(RouteStop.route_id.in_(route_ids)).order_by(RouteStop.stop_sequence)).all() if route_ids else []
    stops_map = {}
    for s in all_stops:
        if s.route_id not in stops_map: stops_map[s.route_id] = []
        stops_map[s.route_id].append(s)

    result = []
    for r in routes:
        driver_name = "Unknown"
        dp_uid = dp_user_map.get(r.driver_id)
        if dp_uid:
            user = driver_user_map.get(dp_uid)
            driver_name = user.full_name if user else "Unknown"

        stops = stops_map.get(r.id, [])
        result.append({
            "id": r.id,
            "route_name": r.route_name,
            "driver_id": r.driver_id,
            "driver_name": driver_name,
            "status": r.status,
            "total_stops": r.total_stops,
            "completed_stops": r.completed_stops,
            "estimated_distance_km": r.estimated_distance_km,
            "estimated_duration_minutes": r.estimated_duration_minutes,
            "created_at": r.created_at.isoformat(),
            "stops": [{"id": s.id, "sequence": s.stop_sequence, "address": s.address, "status": s.status, "type": s.stop_type} for s in stops],
        })
    return result


# ─── RETURNS ──────────────────────────────────────────────────────────────────

@router.get("/returns")
def list_returns(
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    statement = select(ReturnRequest)
    if status:
        statement = statement.where(ReturnRequest.status == status)
    returns = db.exec(statement.order_by(desc(ReturnRequest.created_at))).all()

    user_ids = {r.user_id for r in returns if r.user_id}
    user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    result = []
    for r in returns:
        user = user_map.get(r.user_id)
        result.append({
            "id": r.id,
            "order_id": r.order_id,
            "user_id": r.user_id,
            "user_name": user.full_name if user else "Unknown",
            "reason": r.reason,
            "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
            "refund_amount": r.refund_amount,
            "inspection_notes": r.inspection_notes,
            "created_at": r.created_at.isoformat(),
        })
    return result

@router.get("/returns/stats")
def get_return_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    total = db.exec(select(func.count(ReturnRequest.id))).one()
    pending = db.exec(select(func.count(ReturnRequest.id)).where(ReturnRequest.status == "pending")).one()
    completed = db.exec(select(func.count(ReturnRequest.id)).where(ReturnRequest.status == "completed")).one()
    total_refund = db.exec(select(func.coalesce(func.sum(ReturnRequest.refund_amount), 0))).one()

    return {
        "total_returns": total,
        "pending": pending,
        "completed": completed,
        "total_refund_amount": round(float(total_refund), 2),
    }

@router.put("/returns/{return_id}/status")
def update_return_status(
    return_id: int,
    new_status: str,
    notes: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    ret = db.get(ReturnRequest, return_id)
    if not ret:
        raise HTTPException(404, "Return request not found")
    ret.status = new_status
    if notes:
        ret.inspection_notes = notes
    ret.updated_at = datetime.now(UTC)
    db.add(ret)
    db.commit()
    return {"status": "success"}


# ─── LIVE TRACKING ────────────────────────────────────────────────────────────

@router.get("/tracking")
def get_live_tracking(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Get all active deliveries with driver GPS positions."""
    active_orders = db.exec(
        select(DeliveryOrder).where(DeliveryOrder.status.in_(["assigned", "in_transit"]))
    ).all()

    driver_ids = {o.assigned_driver_id for o in active_orders if o.assigned_driver_id}
    driver_user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(driver_ids))).all()} if driver_ids else {}
    dp_map = {dp.user_id: dp for dp in db.exec(select(DriverProfile).where(DriverProfile.user_id.in_(driver_ids))).all()} if driver_ids else {}

    tracking = []
    for o in active_orders:
        driver_data = None
        if o.assigned_driver_id:
            driver_user = driver_user_map.get(o.assigned_driver_id)
            dp = dp_map.get(o.assigned_driver_id)
            driver_data = {
                "name": driver_user.full_name if driver_user else "Unknown",
                "phone": driver_user.phone_number if driver_user else "",
                "is_online": dp.is_online if dp else False,
                "latitude": dp.current_latitude if dp else None,
                "longitude": dp.current_longitude if dp else None,
                "vehicle_plate": dp.vehicle_plate if dp else "",
            }

        tracking.append({
            "order_id": o.id,
            "order_type": o.order_type.value if hasattr(o.order_type, 'value') else str(o.order_type),
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
            "origin": o.origin_address,
            "destination": o.destination_address,
            "origin_lat": o.origin_lat,
            "origin_lng": o.origin_lng,
            "dest_lat": o.destination_lat,
            "dest_lng": o.destination_lng,
            "driver": driver_data,
            "started_at": o.started_at.isoformat() if o.started_at else None,
        })
    return tracking
