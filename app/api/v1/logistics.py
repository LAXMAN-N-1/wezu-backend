from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session, select
from app.api import deps
from app.db.session import get_session
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

@router.get("/me/assignments", response_model=DataResponse[List[DeliveryOrderResponse]])
def get_my_assignments(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Driver: list of assigned delivery/collection jobs"""
    from app.models.logistics import DeliveryOrder
    from app.models.driver_profile import DriverProfile
    
    driver = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
        
    orders = session.exec(select(DeliveryOrder).where(DeliveryOrder.driver_id == driver.id)).all()
    return DataResponse(success=True, data=orders)

@router.get("/dashboard", response_model=DataResponse[dict])
def get_driver_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
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
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Create a delivery order"""
    order = LogisticsService.create_delivery_order(session, request.dict())
    return DataResponse(success=True, data=order)

@router.get("/orders", response_model=DataResponse[List[DeliveryOrderResponse]])
def list_logistics_orders(
    status: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Admin: list all delivery orders with filters"""
    from app.models.logistics import DeliveryOrder
    statement = select(DeliveryOrder)
    if status:
        statement = statement.where(DeliveryOrder.status == status)
    orders = session.exec(statement).all()
    return DataResponse(success=True, data=orders)

@router.get("/orders/{id}", response_model=DataResponse[dict])
def get_order_details(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Full delivery order details"""
    from app.models.logistics import DeliveryOrder
    order = session.get(DeliveryOrder, id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return DataResponse(success=True, data=order)

@router.put("/orders/{id}/assign", response_model=DataResponse[dict])
def assign_order_to_driver(
    id: int,
    driver_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Assign delivery order to a driver"""
    order = LogisticsService.assign_order(session, id, driver_id)
    return DataResponse(success=True, data={"id": order.id, "status": order.status})

@router.put("/orders/{id}/status", response_model=DataResponse[dict])
def update_order_status(
    id: int,
    status: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Update order status (in transit, delivered, failed)"""
    order = LogisticsService.update_order_status(session, id, status)
    return DataResponse(success=True, data={"id": order.id, "status": order.status})

@router.post("/orders/{id}/pod", response_model=DataResponse[dict])
def upload_order_pod(
    id: int,
    pod_url: str = Body(...),
    signature_url: Optional[str] = Body(None),
    otp: Optional[str] = Body(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Upload proof of delivery"""
    order = LogisticsService.upload_pod(session, id, pod_url, signature_url, otp)
    return DataResponse(success=True, data={"id": order.id, "otp_verified": order.otp_verified})

@router.get("/orders/{id}/pod")
def retrieve_order_pod(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Retrieve proof of delivery for a specific order"""
    from app.models.logistics import DeliveryOrder
    order = session.get(DeliveryOrder, id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"pod_url": order.proof_of_delivery_url, "signature": order.customer_signature_url}

# --- Drivers ---
@router.post("/drivers", response_model=DataResponse[DriverProfileResponse])
def create_driver(
    request: DriverProfileCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Create a new driver profile"""
    from app.services.driver_service import DriverService
    profile = DriverService.create_profile(request.user_id, request.dict(exclude={"user_id"}))
    return DataResponse(success=True, data=profile)

@router.get("/drivers", response_model=DataResponse[List[DriverProfileResponse]])
def list_drivers(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """List all drivers"""
    from app.models.driver_profile import DriverProfile
    drivers = session.exec(select(DriverProfile)).all()
    return DataResponse(success=True, data=drivers)

@router.get("/drivers/{id}", response_model=DataResponse[DriverProfileResponse])
def get_driver_detail(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
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
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
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
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Toggle driver availability"""
    from app.services.driver_service import DriverService
    DriverService.toggle_status(id, is_online)
    return DataResponse(success=True, data={"id": id, "is_online": is_online})

@router.get("/drivers/{id}/performance", response_model=DataResponse[DriverPerformanceResponse])
def get_driver_kp_metrics(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Driver metrics: on-time rate, satisfaction"""
    from app.services.driver_service import DriverService
    perf = DriverService.get_driver_performance(session, id)
    return DataResponse(success=True, data=perf)

@router.post("/routes/optimize", response_model=DataResponse[RouteResponse])
def optimize_driver_route(
    request: RouteOptimizationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Submit multi-stop delivery list and get optimized route"""
    route = LogisticsService.optimize_route(session, request.driver_id, [s.dict() for s in request.stops])
    return DataResponse(success=True, data=route)

@router.get("/orders/{id}/route", response_model=DataResponse[dict])
def get_order_live_route(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Get the active route/ETA for a specific order"""
    from app.models.logistics import DeliveryOrder
    order = session.get(DeliveryOrder, id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
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
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Initiate reverse logistics pickup"""
    rr = LogisticsService.initiate_reverse_pickup(session, request.order_id, current_user.id, request.reason)
    return DataResponse(success=True, data=rr)

@router.get("/returns/{id}", response_model=DataResponse[ReturnResponse])
def get_return_request_detail(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Track status of a specific return request"""
    from app.models.return_request import ReturnRequest
    rr = session.get(ReturnRequest, id)
    if not rr:
        raise HTTPException(status_code=404, detail="Return request not found")
    return DataResponse(success=True, data=rr)

@router.get("/performance", response_model=DataResponse[dict])
def platform_logistics_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Platform-wide delivery metrics dashboard"""
    stats = LogisticsService.get_platform_performance(session)
    return DataResponse(success=True, data=stats)

@router.post("/notifications/delivery-update")
def send_delivery_notification(
    order_id: int,
    message: str,
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Send SMS/Push delivery update"""
    # Trigger notification service
    return {"status": "sent"}
