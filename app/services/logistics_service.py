from typing import Any, List, Optional
from sqlmodel import Session, select, func
from app.core.database import engine
from app.models.logistics import BatteryTransfer, LogisticsManifest as Manifest
from app.models.warehouse import Warehouse
from app.models.delivery_assignment import DeliveryAssignment
from app.models.driver_profile import DriverProfile
from app.models.ecommerce import EcommerceOrder
from app.models.station import Station, StationSlot
from app.models.battery import Battery, LocationType, BatteryStatus
from app.services.notification_service import NotificationService
from datetime import datetime, UTC
from typing import List, Optional, Any

class LogisticsService:
    @staticmethod
    def create_delivery_order(db: Session, data: dict) -> Any:
        from app.models.logistics import DeliveryOrder
        order = DeliveryOrder(**data)
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def assign_order(db: Session, order_id: int, driver_id: int) -> Any:
        from app.models.logistics import DeliveryOrder, DeliveryStatus
        order = db.get(DeliveryOrder, order_id)
        if not order:
            raise ValueError("Order not found")
        
        order.assigned_driver_id = driver_id
        order.status = DeliveryStatus.ASSIGNED
        order.updated_at = datetime.now(UTC)
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def update_order_status(db: Session, order_id: int, status: str) -> Any:
        from app.models.logistics import DeliveryOrder
        order = db.get(DeliveryOrder, order_id)
        if not order:
            raise ValueError("Order not found")
            
        order.status = status
        if status == "in_transit" and not order.started_at:
            order.started_at = datetime.now(UTC)
        elif status == "delivered":
            order.completed_at = datetime.now(UTC)
            # Update driver stats
            if order.assigned_driver_id:
                from app.models.driver_profile import DriverProfile
                driver = db.exec(select(DriverProfile).where(DriverProfile.user_id == order.assigned_driver_id)).first()
                if driver:
                    driver.total_deliveries += 1
                    # Simple on-time logic: if completed - started < 30 mins
                    if order.started_at:
                        duration = (order.completed_at - order.started_at).total_seconds()
                        driver.total_delivery_time_seconds += int(duration)
                        if duration < 1800: # 30 mins
                            driver.on_time_deliveries += 1
                    db.add(driver)

        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def upload_pod(db: Session, order_id: int, pod_url: str, signature_url: str = None, otp: str = None) -> Any:
        from app.models.logistics import DeliveryOrder
        order = db.get(DeliveryOrder, order_id)
        if not order:
            raise ValueError("Order not found")
            
        order.proof_of_delivery_url = pod_url
        if signature_url:
            order.customer_signature_url = signature_url
        if otp and order.completion_otp == otp:
            order.otp_verified = True
            
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def initiate_reverse_pickup(db: Session, order_id: int, user_id: int, reason: str) -> Any:
        from app.models.return_request import ReturnRequest, ReturnStatus
        rr = ReturnRequest(order_id=order_id, user_id=user_id, reason=reason, status=ReturnStatus.PENDING)
        db.add(rr)
        db.commit()
        db.refresh(rr)
        return rr

    @staticmethod
    def optimize_route(db: Session, driver_id: int, stops: List[dict]) -> dict:
        """Simple sequence optimization by distance (Nearest Neighbor)"""
        # In production, use Google Matrix API or similar
        # For now, just return stops in original order but wrap in a route object
        from app.models.delivery_route import DeliveryRoute
        route = DeliveryRoute(driver_id=driver_id, route_name=f"Route {datetime.now(UTC).date()}", total_stops=len(stops))
        db.add(route)
        db.commit()
        db.refresh(route)
        return {"route_id": route.id, "optimized_stops": [s['delivery_assignment_id'] for s in stops], "total_distance_km": 0.0}

    @staticmethod
    def get_platform_performance(db: Session) -> dict:
        """Global logistics metrics"""
        from app.models.logistics import DeliveryOrder
        total = db.exec(select(func.count(DeliveryOrder.id))).one()
        delivered = db.exec(select(func.count(DeliveryOrder.id)).where(DeliveryOrder.status == "delivered")).one()
        
        return {
            "total_orders": total,
            "success_rate": (delivered / total * 100) if total > 0 else 0.0,
            "active_drivers": 0 # Placeholder
        }

    @staticmethod
    def create_manifest(db: Session, driver_id: int, vehicle_id: Optional[str] = None) -> Manifest:
        manifest = Manifest(
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            status="draft"
        )
        db.add(manifest)
        db.commit()
        db.refresh(manifest)
        return manifest

    @staticmethod
    def add_transfer_to_manifest(db: Session, manifest_id: int, transfer_id: int):
        manifest = db.get(Manifest, manifest_id)
        transfer = db.get(BatteryTransfer, transfer_id)
        if manifest and transfer:
            transfer.manifest_id = manifest_id
            transfer.status = "assigned"
            db.add(transfer)
            db.commit()
            db.refresh(transfer)
        return transfer

    @staticmethod
    def start_manifest_trip(db: Session, manifest_id: int):
        manifest = db.get(Manifest, manifest_id)
        if manifest:
            manifest.status = "active"
            db.add(manifest)
            # Update all associated transfers
            for transfer in manifest.transfers:
                transfer.status = "in_transit"
                db.add(transfer)
            db.commit()
            db.refresh(manifest)
        return manifest

    @staticmethod
    def check_and_trigger_restock(db: Session, station_id: int, threshold: int = 2):
        """
        Check if a station needs restocking and create a transfer request if so.
        """
        # Count 'ready' batteries at this station
        from app.models.station import StationSlot
        statement = select(func.count(StationSlot.id)).where(
            StationSlot.station_id == station_id,
            StationSlot.status == "ready"
        )
        ready_count = db.exec(statement).one()
        
        if ready_count < threshold:
            # Need restock. Find nearest warehouse with stock.
            from app.models.warehouse import Warehouse
            warehouse = db.exec(select(Warehouse).where(Warehouse.is_active == True)).first()
            if not warehouse:
                return None
            
            # Find a 'ready' battery in the warehouse
            from app.models.battery import Battery
            battery = db.exec(select(Battery).where(
                Battery.location_type == LocationType.WAREHOUSE,
                Battery.location_id == warehouse.id,
                Battery.status == BatteryStatus.AVAILABLE
            )).first()
            
            if battery:
                transfer = BatteryTransfer(
                    battery_id=battery.id,
                    from_location_type="warehouse",
                    from_location_id=warehouse.id,
                    to_location_type="station",
                    to_location_id=station_id,
                    status="pending"
                )
                db.add(transfer)
                
                # Update battery status to 'maintenance' which acts as a 'transfer_pending' state
                battery.status = BatteryStatus.MAINTENANCE 
                battery.location_type = LocationType.WAREHOUSE
                battery.location_id = warehouse.id
                db.add(battery)
                
                db.commit()
                db.refresh(transfer)
                return transfer
        return None

    @staticmethod
    def bundle_transfers_into_manifest(db: Session, driver_id: int, transfer_ids: List[int]) -> Manifest:
        """
        Group multiple pending transfers into a single manifest for a driver.
        """
        manifest = Manifest(
            driver_id=driver_id,
            status="assigned"
        )
        db.add(manifest)
        db.flush() # Get manifest.id
        
        # Batch-load transfers (eliminates per-id db.get N+1)
        transfers = db.exec(
            select(BatteryTransfer).where(
                BatteryTransfer.id.in_(transfer_ids),
                BatteryTransfer.status == "pending",
            )
        ).all()
        for transfer in transfers:
            transfer.manifest_id = manifest.id
            transfer.status = "assigned"
            db.add(transfer)
        
        db.commit()
        db.refresh(manifest)
        return manifest
