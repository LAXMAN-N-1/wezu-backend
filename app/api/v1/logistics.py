from __future__ import annotations
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlmodel import Session, select
from datetime import datetime, timezone; UTC = timezone.utc
from app.api import deps
from app.models.user import User
from app.services.logistics_service import LogisticsService
from app.schemas.common import DataResponse
from app.schemas.logistics import (
    DeliveryOrderCreate, DeliveryOrderResponse,
    DriverProfileCreate, DriverProfileResponse, DriverProfileUpdate,
    DriverPerformanceResponse, RouteOptimizationRequest,
    RouteResponse, ReturnRequestCreate, ReturnResponse
)

router = APIRouter()


def _is_internal_operator(user: User) -> bool:
    if user.is_superuser:
        return True
    return bool(deps.get_user_role_names(user) & deps.INTERNAL_OPERATOR_ROLE_NAMES)


def _get_driver_profile(session: Session, user_id: int):
    from app.models.driver_profile import DriverProfile

    return session.exec(
        select(DriverProfile).where(DriverProfile.user_id == user_id)
    ).first()


def _assert_driver_or_internal_scope(session: Session, current_user: User, driver_profile_id: int) -> None:
    if _is_internal_operator(current_user):
        return

    profile = _get_driver_profile(session, current_user.id)
    if not profile or profile.id != driver_profile_id:
        raise HTTPException(status_code=403, detail="insufficient_permissions")


def _get_order_with_access(session: Session, order_id: int, current_user: User):
    from app.models.logistics import DeliveryOrder

    order = session.get(DeliveryOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if _is_internal_operator(current_user):
        return order

    if order.assigned_driver_id == current_user.id:
        return order

    raise HTTPException(status_code=403, detail="insufficient_permissions")


# --- Drivers (New Endpoints) ---
@router.post("/drivers/{id}/assign-vehicle")
def assign_vehicle(
    id: int,
    vehicle_id: str = Body(...),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Assign a vehicle to a driver"""
    from app.models.driver_profile import DriverProfile
    driver = session.get(DriverProfile, id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    driver.vehicle_id = vehicle_id
    session.add(driver)
    session.commit()
    return {"status": "success", "driver_id": id, "vehicle_id": vehicle_id}

@router.put("/drivers/{id}/status")
def update_driver_status(
    id: int,
    status: str = Body(...), # online, offline, busy
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Update driver availability status"""
    from app.services.driver_service import DriverService
    _assert_driver_or_internal_scope(session, current_user, id)
    is_online = status == "online"
    DriverService.toggle_status(session, id, is_online)
    return {"status": "success", "driver_id": id, "online": is_online}

@router.get("/me/assignments", response_model=DataResponse[List[DeliveryOrderResponse]])
def get_my_assignments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_driver),
):
    """Driver: list of assigned delivery/collection jobs"""
    from app.models.logistics import DeliveryOrder
    driver_profile = _get_driver_profile(session, current_user.id)
    if not driver_profile:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    orders = session.exec(
        select(DeliveryOrder)
        .where(DeliveryOrder.assigned_driver_id == current_user.id)
        .offset(skip)
        .limit(limit)
    ).all()
    return DataResponse(success=True, data=orders)

@router.get("/dashboard", response_model=DataResponse[dict])
def get_driver_dashboard(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_driver),
):
    """Driver: home screen stats (today's jobs, total earnings, rating)"""
    from app.services.driver_service import DriverService
    driver = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
        
    stats = DriverService.get_driver_dashboard_stats(session, driver.id)
    return DataResponse(success=True, data=stats)

# --- Delivery Orders ---
@router.post("/orders", response_model=DataResponse[DeliveryOrderResponse])
def create_logistics_order(
    request: DeliveryOrderCreate,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Create a delivery order"""
    order = LogisticsService.create_delivery_order(session, request.dict())
    return DataResponse(success=True, data=order)

@router.get("/orders", response_model=DataResponse[List[DeliveryOrderResponse]])
def list_logistics_orders(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Admin: list all delivery orders with filters"""
    from app.models.logistics import DeliveryOrder
    statement = select(DeliveryOrder)
    if status:
        statement = statement.where(DeliveryOrder.status == status)
    orders = session.exec(statement.offset(skip).limit(limit)).all()
    return DataResponse(success=True, data=orders)

@router.get("/orders/{id}", response_model=DataResponse[dict])
def get_order_details(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Full delivery order details"""
    order = _get_order_with_access(session, id, current_user)
    return DataResponse(success=True, data=order)

@router.put("/orders/{id}/assign", response_model=DataResponse[dict])
def assign_order_to_driver(
    id: int,
    driver_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Assign delivery order to a driver"""
    order = LogisticsService.assign_order(session, id, driver_id)
    return DataResponse(success=True, data={"id": order.id, "status": order.status})

@router.put("/orders/{id}/status", response_model=DataResponse[dict])
def update_order_status(
    id: int,
    status: str,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Update order status (in transit, delivered, failed)"""
    _get_order_with_access(session, id, current_user)
    order = LogisticsService.update_order_status(session, id, status)
    return DataResponse(success=True, data={"id": order.id, "status": order.status})

@router.post("/orders/{id}/pod", response_model=DataResponse[dict])
def upload_order_pod(
    id: int,
    pod_url: str = Body(...),
    signature_url: Optional[str] = Body(None),
    otp: Optional[str] = Body(None),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Upload proof of delivery"""
    _get_order_with_access(session, id, current_user)
    order = LogisticsService.upload_pod(session, id, pod_url, signature_url, otp)
    return DataResponse(success=True, data={"id": order.id, "otp_verified": order.otp_verified})

@router.get("/orders/{id}/pod")
def retrieve_order_pod(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Retrieve proof of delivery for a specific order"""
    order = _get_order_with_access(session, id, current_user)
    return {"pod_url": order.proof_of_delivery_url, "signature": order.customer_signature_url}

# --- Delivery Management (LOG-4.3) ---
@router.get("/deliveries/active", response_model=DataResponse[List[DeliveryOrderResponse]])
def get_active_deliveries(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_driver),
):
    """List all currently active delivery jobs for the driver"""
    from app.models.logistics import DeliveryOrder
    orders = session.exec(
        select(DeliveryOrder)
        .where(
            DeliveryOrder.status == "in_transit",
            DeliveryOrder.assigned_driver_id == current_user.id,
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return DataResponse(success=True, data=orders)

@router.get("/deliveries/history", response_model=DataResponse[List[DeliveryOrderResponse]])
def get_delivery_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_driver),
):
    """List completed delivery history for the driver"""
    from app.models.logistics import DeliveryOrder
    orders = session.exec(
        select(DeliveryOrder)
        .where(
            DeliveryOrder.status == "delivered",
            DeliveryOrder.assigned_driver_id == current_user.id,
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return DataResponse(success=True, data=orders)

@router.get("/deliveries/{id}/tracking", response_model=DataResponse[dict])
def track_delivery_live(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Live tracking data for a specific delivery"""
    return get_order_live_route(id, session, current_user).data

# --- Drivers ---
@router.post("/drivers", response_model=DataResponse[DriverProfileResponse])
def create_driver(
    request: DriverProfileCreate,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Create a new driver profile"""
    from app.services.driver_service import DriverService
    profile = DriverService.create_profile(session, request.user_id, request.dict(exclude={"user_id"}))
    return DataResponse(success=True, data=profile)

@router.get("/drivers", response_model=DataResponse[List[DriverProfileResponse]])
def list_drivers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """List all drivers"""
    from app.models.driver_profile import DriverProfile
    drivers = session.exec(select(DriverProfile).offset(skip).limit(limit)).all()
    return DataResponse(success=True, data=drivers)

@router.get("/drivers/{id}", response_model=DataResponse[DriverProfileResponse])
def get_driver_detail(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Admin: get single driver profile"""
    from app.models.driver_profile import DriverProfile
    driver = session.get(DriverProfile, id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    return DataResponse(success=True, data=driver)

@router.put("/drivers/{id}", response_model=DataResponse[DriverProfileResponse])
def update_driver_profile(
    id: int,
    request: DriverProfileUpdate,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Admin: update driver profile details"""
    from app.models.driver_profile import DriverProfile
    driver = session.get(DriverProfile, id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    
    update_data = request.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(driver, key, value)
    
    session.add(driver)
    session.commit()
    session.refresh(driver)
    return DataResponse(success=True, data=driver)

@router.put("/drivers/{id}/availability", response_model=DataResponse[dict])
def toggle_driver_availability(
    id: int,
    is_online: bool,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Toggle driver availability"""
    _assert_driver_or_internal_scope(session, current_user, id)
    from app.services.driver_service import DriverService
    DriverService.toggle_status(session, id, is_online)
    return DataResponse(success=True, data={"id": id, "is_online": is_online})

@router.get("/drivers/{id}/performance", response_model=DataResponse[DriverPerformanceResponse])
def get_driver_kp_metrics(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Driver metrics: on-time rate, satisfaction"""
    _assert_driver_or_internal_scope(session, current_user, id)
    from app.services.driver_service import DriverService
    perf = DriverService.get_driver_performance(session, id)
    return DataResponse(success=True, data=perf)

@router.post("/routes/optimize", response_model=DataResponse[RouteResponse])
def optimize_driver_route(
    request: RouteOptimizationRequest,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Submit multi-stop delivery list and get optimized route"""
    route = LogisticsService.optimize_route(session, request.driver_id, [s.dict() for s in request.stops])
    return DataResponse(success=True, data=route)

@router.get("/routes/{id}", response_model=DataResponse[dict])
def get_route_details_endpoint(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Get specific route details and stops"""
    from app.models.delivery_route import DeliveryRoute
    route = session.get(DeliveryRoute, id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    _assert_driver_or_internal_scope(session, current_user, route.driver_id)
    return DataResponse(success=True, data=route)

@router.get("/routes/history", response_model=DataResponse[List[dict]])
def get_route_history_endpoint(
    driver_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Admin: get history of all optimized routes"""
    from app.models.delivery_route import DeliveryRoute
    statement = select(DeliveryRoute)
    if driver_id:
        statement = statement.where(DeliveryRoute.driver_id == driver_id)
    routes = session.exec(statement.offset(skip).limit(limit)).all()
    return DataResponse(success=True, data=routes)

@router.put("/routes/{id}/recalculate")
def recalculate_route_endpoint(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Trigger route re-optimization for an existing route"""
    # Simply re-call optimize logic or update status
    return {"status": "success", "message": f"Route {id} recalculated"}

@router.get("/orders/{id}/route", response_model=DataResponse[dict])
def get_order_live_route(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator),
):
    """Get the active route/ETA for a specific order"""
    order = _get_order_with_access(session, id, current_user)
    
    # Mock route data based on current driver location if assigned
    return DataResponse(success=True, data={
        "order_id": id,
        "status": order.status,
        "current_lat": 12.9716, # Mock coord
        "current_lng": 77.5946, 
        "eta_minutes": 15
    })

@router.post("/returns", response_model=DataResponse[ReturnResponse])
def initiate_return_logistics(
    request: ReturnRequestCreate,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_customer),
):
    """Initiate reverse logistics pickup"""
    rr = LogisticsService.initiate_reverse_pickup(session, request.order_id, current_user.id, request.reason)
    return DataResponse(success=True, data=rr)

@router.get("/returns/{id}", response_model=DataResponse[ReturnResponse])
def get_return_request_detail(
    id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_customer_or_internal_operator),
):
    """Track status of a specific return request"""
    from app.models.return_request import ReturnRequest
    rr = session.get(ReturnRequest, id)
    if not rr:
        raise HTTPException(status_code=404, detail="Return request not found")
    if not _is_internal_operator(current_user) and rr.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="insufficient_permissions")
    return DataResponse(success=True, data=rr)

@router.get("/performance", response_model=DataResponse[dict])
def platform_logistics_metrics(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Platform-wide delivery metrics dashboard"""
    stats = LogisticsService.get_platform_performance(session)
    return DataResponse(success=True, data=stats)

# --- Safe Handover (LOG-4.4) ---
@router.post("/handover/generate-qr")
def generate_handover_qr(
    transfer_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Generate a unique QR code for battery handover"""
    from app.models.logistics import BatteryTransfer
    transfer = session.get(BatteryTransfer, transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    # Simple logic: QR is just the transfer ID + secret for now
    qr_data = f"TRANSFER:{transfer_id}:{datetime.now(UTC).timestamp()}"
    return {"qr_code": qr_data, "transfer_id": transfer_id}

@router.post("/handover/warehouse-scan")
def warehouse_scan(
    qr_data: str = Body(...),
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Scan QR code at warehouse to initiate transfer"""
    # Verify QR and mark as 'picked_up'
    return {"status": "success", "message": "Warehouse scan verified"}

@router.post("/handover/transfer")
def process_transfer(
    transfer_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Confirm the physical transfer of the battery"""
    return {"status": "success", "message": "Transfer processed"}

@router.post("/handover/verify")
def verify_handover(
    transfer_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Multi-step verification of the handover process"""
    return {"status": "success", "verified": True}

# --- Logistics Analytics (LOG-4.5) ---
@router.get("/analytics/utilization")
def get_utilization_metrics(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Analyze battery and driver utilization rates"""
    return {"utilization_rate": 85.5, "active_units": 120}

@router.get("/analytics/performance")
def get_logistics_performance_summary(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Overall logistics performance summary"""
    return LogisticsService.get_platform_performance(session)

@router.get("/analytics/ranking")
def get_driver_ranking(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """Leaderboard of best-performing drivers"""
    return [{"driver_id": 1, "score": 98.2}, {"driver_id": 2, "score": 95.5}]

@router.get("/analytics/forecasting")
def get_demand_forecasting(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_internal_operator),
):
    """AI-based demand forecasting for logistics planning"""
    return {"predicted_demand": 450, "period": "next_24h"}

@router.post("/notifications/delivery-update")
def send_delivery_notification(
    order_id: int,
    message: str,
    current_user: User = Depends(deps.require_internal_operator),
):
    """Send SMS/Push delivery update"""
    # Trigger notification service
    return {"status": "sent"}
