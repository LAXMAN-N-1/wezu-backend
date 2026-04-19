from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import DataResponse
from app.schemas.route import (
    LocationBase,
    OptimizedWaypoint,
    RouteOptimizeRequest,
    RouteOptimizeResponse,
)
from app.services.route_service import RouteOptimizationInputError, get_route_service

router = APIRouter()


@router.post("/optimize", response_model=DataResponse[RouteOptimizeResponse])
def optimize_route(
    request: RouteOptimizeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Optimize delivery route sequence for a driver and set of orders.
    """
    route_service = get_route_service(session)
    try:
        route = route_service.optimize_driver_route(
            request.driver_id,
            {"lat": request.start_location.lat, "lng": request.start_location.lng},
            request.order_ids,
        )
    except RouteOptimizationInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not route:
        raise HTTPException(
            status_code=503,
            detail="Route optimization is temporarily unavailable. Please retry shortly.",
        )

    optimized_waypoints = []
    for waypoint in route["waypoints"]:
        estimated_arrival = waypoint["estimated_arrival"]
        if isinstance(estimated_arrival, str):
            estimated_arrival = datetime.fromisoformat(estimated_arrival)

        optimized_waypoints.append(
            OptimizedWaypoint(
                sequence_index=waypoint["sequence_index"],
                order_id=waypoint["order_id"],
                location=LocationBase(
                    lat=waypoint["location"]["lat"],
                    lng=waypoint["location"]["lng"],
                ),
                estimated_arrival=estimated_arrival,
            )
        )

    response_data = RouteOptimizeResponse(
        route_id=UUID(route["id"]),
        optimized_waypoints=optimized_waypoints,
        overview_polyline=route["polyline"],
        total_distance_meters=route["distance_meters"],
        total_duration_seconds=route["duration_seconds"],
        traffic_congestion_level=route["traffic_congestion_level"],
    )

    return DataResponse(success=True, data=response_data)
