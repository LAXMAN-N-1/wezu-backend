from sqlmodel import Session, select
from app.core.database import engine
from app.models.logistics import DeliveryAssignment, DriverProfile, BatteryTransfer, Warehouse
from app.models.ecommerce import Order
from app.models.station import Station, StationSlot
from app.models.battery import Battery
from app.services.notification_service import NotificationService
from datetime import datetime
from sqlmodel import func, select

class LogisticsService:
    
    @staticmethod
    def create_delivery_for_order(order_id: int, pickup_address: str, delivery_address: str) -> DeliveryAssignment:
        with Session(engine) as session:
            assignment = DeliveryAssignment(
                order_id=order_id,
                status="PENDING",
                pickup_address=pickup_address,
                delivery_address=delivery_address
            )
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            return assignment

    @staticmethod
    def assign_driver(delivery_id: int, driver_id: int) -> DeliveryAssignment:
        with Session(engine) as session:
            delivery = session.get(DeliveryAssignment, delivery_id)
            if not delivery:
                raise ValueError("Delivery not found")
            
            driver = session.get(DriverProfile, driver_id)
            if not driver:
                raise ValueError("Driver not found")
            
            delivery.driver_id = driver_id
            delivery.status = "ASSIGNED"
            delivery.assigned_at = datetime.utcnow()
            
            session.add(delivery)
            session.commit()
            session.refresh(delivery)
            
            # Notify Driver
            NotificationService.send_push_notification(
                user_id=driver.user_id,
                title="New Delivery Assigned",
                body=f"Pickup: {delivery.pickup_address}"
            )
            
            return delivery

    @staticmethod
    def update_delivery_status(delivery_id: int, status: str, pod_img: str = None, signature: str = None) -> DeliveryAssignment:
        with Session(engine) as session:
            delivery = session.get(DeliveryAssignment, delivery_id)
            if not delivery:
                raise ValueError("Delivery not found")
            
            delivery.status = status
            
            if status == "PICKED_UP":
                delivery.picked_up_at = datetime.utcnow()
                # Update Order Status
                if delivery.order_id:
                     order = session.get(Order, delivery.order_id)
                     order.status = "shipped"
                     session.add(order)
            
            elif status == "DELIVERED":
                delivery.delivered_at = datetime.utcnow()
                delivery.proof_of_delivery_img = pod_img
                delivery.customer_signature = signature
                
                # Update Order Status
                if delivery.order_id:
                     order = session.get(Order, delivery.order_id)
                     order.status = "delivered"
                     session.add(order)
                
                # Update Driver Stats
                if delivery.driver_id:
                    driver = session.get(DriverProfile, delivery.driver_id)
                    driver.total_deliveries += 1
                    session.add(driver)

            session.add(delivery)
            session.commit()
            session.refresh(delivery)
            return delivery

    @staticmethod
    def check_and_trigger_restock(db: Session, station_id: int, threshold: int = 2):
        """
        Check if a station needs restocking and create a transfer request if so.
        """
        # Count 'ready' batteries at this station
        statement = select(func.count(StationSlot.id)).where(
            StationSlot.station_id == station_id,
            StationSlot.status == "ready"
        )
        ready_count = db.exec(statement).one()
        
        if ready_count < threshold:
            # Need restock. Find nearest warehouse with stock.
            # (Simplified distance logic for now)
            warehouse = db.exec(select(Warehouse).where(Warehouse.is_active == True)).first()
            if not warehouse:
                return None
            
            # Find a 'ready' battery in the warehouse
            battery = db.exec(select(Battery).where(
                Battery.location_type == "warehouse",
                Battery.location_id == warehouse.id,
                Battery.status == "ready"
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
                
                # Update battery status to 'in_transit' effectively
                battery.status = "in_transit" 
                db.add(battery)
                
                db.commit()
                db.refresh(transfer)
                return transfer
        return None

