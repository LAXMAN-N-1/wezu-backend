from __future__ import annotations
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlmodel import Session, select

from app.integrations.google_maps import google_maps_integration
from app.models.driver_profile import DriverProfile
from app.models.order import Order

logger = logging.getLogger(__name__)
ROUTABLE_ORDER_STATUSES = {"pending", "in_transit"}


class RouteOptimizationInputError(ValueError):
    """Raised when route optimization input is semantically invalid."""


class RouteService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_geocode_order_location(self, order: Order) -> Optional[Tuple[float, float]]:
        """Ensure order has coordinates, geocode if necessary."""
        if order.latitude is not None and order.longitude is not None:
            return order.latitude, order.longitude

        if not order.destination:
            return None

        logger.info("Geocoding order %s destination: %s", order.id, order.destination)
        geo_result = google_maps_integration.geocode_address(order.destination)
        if not geo_result:
            return None

        order.latitude = geo_result["latitude"]
        order.longitude = geo_result["longitude"]
        self.db.add(order)
        self.db.flush()
        return order.latitude, order.longitude

    def optimize_driver_route(
        self,
        driver_id: int,
        start_location: Dict[str, float],
        order_ids: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate optimized route for a driver and orders.
        Returns response-ready route data; this method does not persist route rows.
        """
        try:
            if not order_ids:
                raise RouteOptimizationInputError("No order IDs provided")
            if len(set(order_ids)) != len(order_ids):
                raise RouteOptimizationInputError("Duplicate order IDs are not allowed")
            if "lat" not in start_location or "lng" not in start_location:
                raise RouteOptimizationInputError("start_location must include lat/lng keys")

            driver = self.db.exec(select(DriverProfile).where(DriverProfile.id == driver_id)).first()
            if not driver:
                raise RouteOptimizationInputError(f"Driver '{driver_id}' not found")

            orders = self.db.exec(select(Order).where(Order.id.in_(order_ids))).all()
            if not orders:
                raise RouteOptimizationInputError("None of the requested orders were found")

            order_map = {str(order.id): order for order in orders}
            missing_order_ids = [order_id for order_id in order_ids if order_id not in order_map]
            if missing_order_ids:
                raise RouteOptimizationInputError(
                    f"Orders not found: {sorted(missing_order_ids)}"
                )

            invalid_status_orders = sorted(
                str(order.id)
                for order in orders
                if order.status not in ROUTABLE_ORDER_STATUSES
            )
            if invalid_status_orders:
                raise RouteOptimizationInputError(
                    "Orders must be pending/in_transit for route optimization: "
                    f"{invalid_status_orders}"
                )

            ordered_orders = [order_map[order_id] for order_id in order_ids]

            valid_orders: List[Order] = []
            order_coords: List[Tuple[float, float]] = []
            unresolved_order_ids: List[str] = []
            for order in ordered_orders:
                coords = self.get_or_geocode_order_location(order)
                if coords:
                    valid_orders.append(order)
                    order_coords.append(coords)
                else:
                    unresolved_order_ids.append(str(order.id))

            if unresolved_order_ids:
                raise RouteOptimizationInputError(
                    "Missing coordinates for orders (and geocoding failed): "
                    f"{sorted(unresolved_order_ids)}"
                )

            # Coordinates may have been filled by geocoding.
            self.db.commit()

            origin = (start_location["lat"], start_location["lng"])
            destination = order_coords[-1]
            waypoints = order_coords[:-1]

            directions = google_maps_integration.get_directions(
                origin=origin,
                destination=destination,
                waypoints=waypoints,
                optimize_waypoints=True,
                departure_time="now",
            )
            if not directions:
                logger.warning("Google Maps directions unavailable; using deterministic fallback routing")
                return self._build_fallback_route(
                    origin=origin,
                    orders=valid_orders,
                    order_coords=order_coords,
                )

            legs = directions.get("legs", [])
            if not legs:
                logger.warning("Google Maps directions missing legs; using deterministic fallback routing")
                return self._build_fallback_route(
                    origin=origin,
                    orders=valid_orders,
                    order_coords=order_coords,
                )

            waypoint_indices = directions.get("waypoint_order", list(range(max(len(valid_orders) - 1, 0))))
            current_time = datetime.utcnow()
            cumulative_duration_seconds = 0
            optimized_waypoints = []

            if len(valid_orders) == 1:
                cumulative_duration_seconds += int(legs[0].get("duration_seconds", 0))
                only_order = valid_orders[0]
                optimized_waypoints.append(
                    {
                        "sequence_index": 0,
                        "order_id": str(only_order.id),
                        "location": {
                            "lat": float(only_order.latitude),
                            "lng": float(only_order.longitude),
                        },
                        "estimated_arrival": (
                            current_time + timedelta(seconds=cumulative_duration_seconds)
                        ).isoformat(),
                    }
                )
            else:
                ordered_stop_indices = waypoint_indices + [len(valid_orders) - 1]
                if len(ordered_stop_indices) != len(legs):
                    logger.warning(
                        "Leg count mismatch (stops=%s legs=%s); using deterministic fallback routing",
                        len(ordered_stop_indices),
                        len(legs),
                    )
                    return self._build_fallback_route(
                        origin=origin,
                        orders=valid_orders,
                        order_coords=order_coords,
                    )

                for sequence_index, order_index in enumerate(ordered_stop_indices):
                    leg = legs[sequence_index]
                    cumulative_duration_seconds += int(leg.get("duration_seconds", 0))
                    order = valid_orders[order_index]
                    optimized_waypoints.append(
                        {
                            "sequence_index": sequence_index,
                            "order_id": str(order.id),
                            "location": {
                                "lat": float(order.latitude),
                                "lng": float(order.longitude),
                            },
                            "estimated_arrival": (
                                current_time + timedelta(seconds=cumulative_duration_seconds)
                            ).isoformat(),
                        }
                    )

            return {
                "id": str(uuid4()),
                "waypoints": optimized_waypoints,
                "polyline": directions.get("polyline", ""),
                "distance_meters": int(directions.get("distance_meters", 0)),
                "duration_seconds": int(directions.get("duration_seconds", 0)),
                "traffic_congestion_level": directions.get("traffic_congestion_level", "moderate"),
            }

        except RouteOptimizationInputError:
            self.db.rollback()
            raise
        except Exception as exc:
            logger.exception("Unexpected error in route optimization: %s", exc)
            self.db.rollback()
            return None

    def _build_fallback_route(
        self,
        *,
        origin: Tuple[float, float],
        orders: List[Order],
        order_coords: List[Tuple[float, float]],
    ) -> Dict[str, Any]:
        current_time = datetime.utcnow()
        cumulative_duration_seconds = 0
        cumulative_distance_meters = 0
        optimized_waypoints: List[Dict[str, Any]] = []

        prev_point = origin
        for sequence_index, (order, point) in enumerate(zip(orders, order_coords)):
            leg_distance = int(self._haversine_meters(prev_point, point))
            # Assume 30km/h fallback speed with a minimum 1 minute per stop.
            leg_duration = max(int(leg_distance / 8.33), 60)
            cumulative_distance_meters += leg_distance
            cumulative_duration_seconds += leg_duration
            optimized_waypoints.append(
                {
                    "sequence_index": sequence_index,
                    "order_id": str(order.id),
                    "location": {
                        "lat": float(point[0]),
                        "lng": float(point[1]),
                    },
                    "estimated_arrival": (
                        current_time + timedelta(seconds=cumulative_duration_seconds)
                    ).isoformat(),
                }
            )
            prev_point = point

        return {
            "id": str(uuid4()),
            "waypoints": optimized_waypoints,
            "polyline": "",
            "distance_meters": cumulative_distance_meters,
            "duration_seconds": cumulative_duration_seconds,
            "traffic_congestion_level": "low",
        }

    @staticmethod
    def _haversine_meters(
        point_a: Tuple[float, float],
        point_b: Tuple[float, float],
    ) -> float:
        lat1, lon1 = point_a
        lat2, lon2 = point_b

        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)

        a = sin(d_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(d_lon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371000 * c


def get_route_service(db: Session) -> RouteService:
    return RouteService(db)
