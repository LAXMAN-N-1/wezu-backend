"""
Order Service
Order creation, management, and fulfillment
"""
from sqlmodel import Session, select
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from app.models.catalog import CatalogOrder, CatalogOrderItem, DeliveryTracking, DeliveryEvent, CatalogProduct, CatalogProductVariant as ProductVariant
from app.services.catalog_service import CatalogService
import logging

logger = logging.getLogger(__name__)

class OrderService:
    """Order management service"""
    
    @staticmethod
    def create_order(
        user_id: int,
        items: List[Dict],
        shipping_address: Dict,
        payment_method: str,
        session: Session
    ) -> Optional[CatalogOrder]:
        """
        Create new order
        
        Args:
            user_id: User ID
            items: List of {product_id, variant_id, quantity}
            shipping_address: Shipping details
            payment_method: Payment method
            session: Database session
            
        Returns:
            Created order or None
        """
        try:
            # Validate and calculate totals
            subtotal = 0
            order_items = []
            
            for item in items:
                product_id = item['product_id']
                variant_id = item.get('variant_id')
                quantity = item['quantity']
                
                # Check stock availability
                if not CatalogService.check_stock_availability(
                    product_id, variant_id, quantity, session
                ):
                    raise ValueError(f"Insufficient stock for product {product_id}")
                
                # Get product details
                product = session.get(CatalogProduct, product_id)
                if not product:
                    raise ValueError(f"Product {product_id} not found")
                
                # Determine price
                if variant_id:
                    variant = session.get(ProductVariant, variant_id)
                    unit_price = variant.price or product.price
                    sku = variant.sku
                else:
                    unit_price = product.price
                    sku = product.sku
                
                total_price = unit_price * quantity
                subtotal += total_price
                
                order_items.append({
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'product_name': product.name,
                    'sku': sku,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total_price': total_price,
                    'warranty_months': product.warranty_months
                })
            
            # Calculate tax and shipping
            tax_amount = subtotal * 0.18  # 18% GST
            shipping_fee = 0 if subtotal > 500 else 50  # Free shipping above ₹500
            total_amount = subtotal + tax_amount + shipping_fee
            
            # Generate order number
            order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            
            # Create order
            order = CatalogOrder(
                order_number=order_number,
                user_id=user_id,
                subtotal=subtotal,
                tax_amount=tax_amount,
                shipping_fee=shipping_fee,
                total_amount=total_amount,
                shipping_address=shipping_address['address'],
                shipping_city=shipping_address['city'],
                shipping_state=shipping_address['state'],
                shipping_pincode=shipping_address['pincode'],
                shipping_phone=shipping_address['phone'],
                payment_method=payment_method,
                status="PENDING"
            )
            session.add(order)
            session.flush()  # Get order ID
            
            # Create order items and reserve stock
            for item_data in order_items:
                order_item = CatalogOrderItem(
                    order_id=order.id,
                    **item_data
                )
                session.add(order_item)
                
                # Reserve stock
                CatalogService.reserve_stock(
                    item_data['product_id'],
                    item_data['variant_id'],
                    item_data['quantity'],
                    session
                )
            
            session.commit()
            session.refresh(order)
            
            return order
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create order: {str(e)}")
            return None
    
    @staticmethod
    def confirm_order(order_id: int, payment_id: str, session: Session) -> bool:
        """Confirm order after successful payment"""
        try:
            order = session.get(CatalogOrder, order_id)
            if not order:
                return False
            
            order.status = "CONFIRMED"
            order.payment_status = "PAID"
            order.payment_id = payment_id
            order.confirmed_at = datetime.utcnow()
            
            session.add(order)
            session.commit()
            
            # Create delivery tracking
            OrderService.create_delivery_tracking(order_id, session)
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to confirm order: {str(e)}")
            return False
    
    @staticmethod
    def cancel_order(order_id: int, reason: str, session: Session) -> bool:
        """Cancel order and release stock"""
        try:
            order = session.get(CatalogOrder, order_id)
            if not order:
                return False
            
            if order.status not in ["PENDING", "CONFIRMED"]:
                raise ValueError("Order cannot be cancelled")
            
            # Release stock
            items = session.exec(
                select(CatalogOrderItem).where(CatalogOrderItem.order_id == order_id)
            ).all()
            
            for item in items:
                CatalogService.release_stock(
                    item.product_id,
                    item.variant_id,
                    item.quantity,
                    session
                )
            
            order.status = "CANCELLED"
            order.cancelled_at = datetime.utcnow()
            order.admin_notes = reason
            
            session.add(order)
            session.commit()
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to cancel order: {str(e)}")
            return False
    
    @staticmethod
    def create_delivery_tracking(order_id: int, session: Session) -> Optional[DeliveryTracking]:
        """Create delivery tracking for order"""
        try:
            # Generate tracking number
            tracking_number = f"TRK-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:10].upper()}"
            
            tracking = DeliveryTracking(
                order_id=order_id,
                tracking_number=tracking_number,
                courier_name="BlueDart",  # Default courier
                current_status="PENDING"
            )
            session.add(tracking)
            session.commit()
            session.refresh(tracking)
            
            # Create initial event
            event = DeliveryEvent(
                tracking_id=tracking.id,
                status="PENDING",
                description="Order confirmed, preparing for shipment"
            )
            session.add(event)
            session.commit()
            
            return tracking
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create delivery tracking: {str(e)}")
            return None
    
    @staticmethod
    def update_delivery_status(
        tracking_id: int,
        status: str,
        location: Optional[str],
        description: str,
        session: Session
    ) -> bool:
        """Update delivery status"""
        try:
            tracking = session.get(DeliveryTracking, tracking_id)
            if not tracking:
                return False
            
            tracking.current_status = status
            if location:
                tracking.current_location = location
            tracking.updated_at = datetime.utcnow()
            
            # Create event
            event = DeliveryEvent(
                tracking_id=tracking_id,
                status=status,
                location=location,
                description=description
            )
            
            session.add(tracking)
            session.add(event)
            session.commit()
            
            # Update order status if delivered
            if status == "DELIVERED":
                order = session.get(CatalogOrder, tracking.order_id)
                if order:
                    order.status = "DELIVERED"
                    order.delivered_at = datetime.utcnow()
                    tracking.actual_delivery_date = datetime.utcnow()
                    session.add(order)
                    session.commit()
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update delivery status: {str(e)}")
            return False
