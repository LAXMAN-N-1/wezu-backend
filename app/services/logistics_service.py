from sqlmodel import Session, select
from app.core.database import engine
from app.models.logistics import DeliveryAssignment, DriverProfile
from app.models.ecommerce import Order
from app.services.notification_service import NotificationService
from datetime import datetime

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
