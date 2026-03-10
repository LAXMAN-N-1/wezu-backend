"""
Product Catalog API
Browse, search, and purchase products
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.models.catalog import CatalogOrder, CatalogOrderItem
from app.services.catalog_service import CatalogService
from app.services.order_service import OrderService
from app.services.invoice_service import InvoiceService
from app.schemas.common import DataResponse
from app.schemas.catalog import (
    ProductCreate, ProductUpdate, ProductResponse, 
    CategoryListResponse, OrderReturnRequest
)
from fastapi.responses import StreamingResponse

router = APIRouter()

# Schemas
class ProductSearchRequest(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_capacity: Optional[int] = None
    max_capacity: Optional[int] = None
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    in_stock_only: bool = True
    sort_by: str = "featured"  # featured, price_asc, price_desc, rating, popularity, newest
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

class OrderItemRequest(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(..., gt=0)

class ShippingAddressRequest(BaseModel):
    address: str
    city: str
    state: str
    pincode: str = Field(..., pattern=r'^\d{6}$')
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{9,14}$')

class OrderCreateRequest(BaseModel):
    items: List[OrderItemRequest]
    shipping_address: ShippingAddressRequest
    payment_method: str = "RAZORPAY"
    customer_notes: Optional[str] = None

# Catalog Endpoints

@router.get("/products/categories", response_model=DataResponse[CategoryListResponse])
def get_product_categories(
    session: Session = Depends(deps.get_db)
):
    """List of product categories"""
    metadata = CatalogService.get_catalog_metadata(session)
    return DataResponse(success=True, data={"categories": metadata["categories"]})

# Admin Product Management
@router.post("/admin/products", response_model=DataResponse[dict])
def admin_create_product(
    request: ProductCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: create a new product listing"""
    product = CatalogService.create_product(request, session)
    return DataResponse(success=True, data={"id": product.id, "message": "Product created"})

@router.put("/admin/products/{id}", response_model=DataResponse[dict])
def admin_update_product(
    id: int,
    request: ProductUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: update product details or pricing"""
    product = CatalogService.update_product(id, request, session)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return DataResponse(success=True, data={"id": product.id, "message": "Product updated"})

@router.delete("/admin/products/{id}", response_model=DataResponse[dict])
def admin_delete_product(
    id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: deactivate/remove a product"""
    success = CatalogService.delete_product(id, session)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return DataResponse(success=True, data={"message": "Product deactivated"})

# Catalog Endpoints (continued)
@router.post("/products/search", response_model=DataResponse[dict])
def search_products(
    request: ProductSearchRequest,
    session: Session = Depends(deps.get_db)
):
    """
    Search and filter products (POST version)
    """
    offset = (request.page - 1) * request.page_size
    
    products, total_count = CatalogService.search_products(
        query=request.query,
        category=request.category,
        brand=request.brand,
        min_price=request.min_price,
        max_price=request.max_price,
        min_capacity=request.min_capacity,
        max_capacity=request.max_capacity,
        min_rating=request.min_rating,
        in_stock_only=request.in_stock_only,
        sort_by=request.sort_by,
        limit=request.page_size,
        offset=offset,
        session=session
    )
    
    return DataResponse(
        success=True,
        data={
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "brand": p.brand,
                    "price": p.price,
                    "original_price": p.original_price,
                    "discount_percentage": p.discount_percentage,
                    "capacity_mah": p.capacity_mah,
                    "warranty_months": p.warranty_months,
                    "average_rating": p.average_rating,
                    "review_count": p.review_count,
                    "in_stock": p.stock_quantity > 0,
                    "is_featured": p.is_featured,
                    "sku": p.sku,
                    "battery_type": p.battery_type,
                    "image_url": p.images[0].image_url if p.images else None
                }
                for p in products
            ],
            "total_count": total_count,
            "page": request.page,
            "page_size": request.page_size,
            "total_pages": (total_count + request.page_size - 1) // request.page_size
        }
    )

@router.get("/products", response_model=DataResponse[dict])
def get_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: str = "featured",
    page: int = 1,
    page_size: int = 20,
    session: Session = Depends(deps.get_db)
):
    """
    Search and filter products (GET version)
    """
    offset = (page - 1) * page_size
    
    products, total_count = CatalogService.search_products(
        query=q,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_capacity=None,
        max_capacity=None,
        min_rating=None,
        in_stock_only=True,
        sort_by=sort_by,
        limit=page_size,
        offset=offset,
        session=session
    )
    
    return DataResponse(
        success=True,
        data={
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "brand": p.brand,
                    "price": p.price,
                    "original_price": p.original_price,
                    "discount_percentage": p.discount_percentage,
                    "capacity_mah": p.capacity_mah,
                    "warranty_months": p.warranty_months,
                    "average_rating": p.average_rating,
                    "review_count": p.review_count,
                    "in_stock": p.stock_quantity > 0,
                    "is_featured": p.is_featured,
                    "sku": p.sku,
                    "battery_type": p.battery_type,
                    "image_url": p.images[0].image_url if p.images else None
                }
                for p in products
            ],
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    )
@router.get("/products/metadata", response_model=DataResponse[dict])
def get_catalog_metadata(
    session: Session = Depends(deps.get_db)
):
    """Get unique categories, brands, and price ranges for filtering"""
    metadata = CatalogService.get_catalog_metadata(session)
    return DataResponse(success=True, data=metadata)

@router.get("/products/{product_id}", response_model=DataResponse[dict])
def get_product_details(
    product_id: int,
    session: Session = Depends(deps.get_db)
):
    """Get complete product details with images and variants"""
    details = CatalogService.get_product_details(product_id, session)
    
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    product = details['product']
    
    return DataResponse(
        success=True,
        data={
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "brand": product.brand,
            "model": product.model,
            "sku": product.sku,
            "price": product.price,
            "original_price": product.original_price,
            "discount_percentage": product.discount_percentage,
            "capacity_mah": product.capacity_mah,
            "voltage": product.voltage,
            "battery_type": product.battery_type,
            "warranty_months": product.warranty_months,
            "warranty_terms": product.warranty_terms,
            "stock_quantity": product.stock_quantity,
            "average_rating": product.average_rating,
            "review_count": product.review_count,
            "in_stock": details['in_stock'],
            "images": [
                {
                    "url": img.image_url,
                    "alt_text": img.alt_text,
                    "is_primary": img.is_primary
                }
                for img in details['images']
            ],
            "variants": [
                {
                    "id": v.id,
                    "name": v.variant_name,
                    "sku": v.sku,
                    "price": v.price or product.price,
                    "stock_quantity": v.stock_quantity,
                    "color": v.color,
                    "capacity_mah": v.capacity_mah
                }
                for v in details['variants']
            ]
        }
    )

@router.get("/products/featured", response_model=DataResponse[list])
def get_featured_products(
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(deps.get_db)
):
    """Get featured products"""
    products = CatalogService.get_featured_products(limit, session)
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "price": p.price,
                "discount_percentage": p.discount_percentage,
                "average_rating": p.average_rating
            }
            for p in products
        ]
    )

# Order Endpoints

@router.get("/admin/catalog/orders", response_model=DataResponse[list])
def admin_get_orders(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: all orders paginated with filters"""
    orders = OrderService.get_admin_orders(session, status, user_id, skip, limit)
    return DataResponse(success=True, data=orders)

@router.post("/orders", response_model=DataResponse[dict])
def create_order(
    request: OrderCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """
    Create new order
    Customer selects products and creates order
    """
    # Convert request to service format
    items = [
        {
            'product_id': item.product_id,
            'variant_id': item.variant_id,
            'quantity': item.quantity
        }
        for item in request.items
    ]
    
    shipping_address = {
        'address': request.shipping_address.address,
        'city': request.shipping_address.city,
        'state': request.shipping_address.state,
        'pincode': request.shipping_address.pincode,
        'phone': request.shipping_address.phone
    }
    
    order = OrderService.create_order(
        user_id=current_user.id,
        items=items,
        shipping_address=shipping_address,
        payment_method=request.payment_method,
        session=session
    )
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create order"
        )
    
    return DataResponse(
        success=True,
        data={
            "order_id": order.id,
            "order_number": order.order_number,
            "total_amount": order.total_amount,
            "status": order.status,
            "payment_method": order.payment_method,
            "message": "Order created successfully. Proceed to payment."
        }
    )

@router.get("/orders/{order_id}", response_model=DataResponse[dict])
def get_order_details(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Get order details"""
    order = session.get(CatalogOrder, order_id)
    
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Get order items
    from sqlmodel import select
    items = session.exec(
        select(CatalogOrderItem).where(CatalogOrderItem.order_id == order_id)
    ).all()
    
    return DataResponse(
        success=True,
        data={
            "order_number": order.order_number,
            "status": order.status,
            "subtotal": order.subtotal,
            "tax_amount": order.tax_amount,
            "shipping_fee": order.shipping_fee,
            "total_amount": order.total_amount,
            "payment_status": order.payment_status,
            "created_at": order.created_at.isoformat(),
            "items": [
                {
                    "product_name": item.product_name,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price
                }
                for item in items
            ]
        }
    )

@router.get("/orders", response_model=DataResponse[list])
def get_user_orders(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Get all orders for current user"""
    from sqlmodel import select
    
    orders = session.exec(
        select(CatalogOrder)
        .where(CatalogOrder.user_id == current_user.id)
        .order_by(CatalogOrder.created_at.desc())
    ).all()
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": order.id,
                "order_number": order.order_number,
                "total_amount": order.total_amount,
                "status": order.status,
                "payment_status": order.payment_status,
                "created_at": order.created_at.isoformat()
            }
            for order in orders
        ]
    )

@router.post("/orders/{order_id}/cancel", response_model=DataResponse[dict])
def cancel_order(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Cancel order"""
    order = session.get(CatalogOrder, order_id)
    
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    success = OrderService.cancel_order(order_id, "Cancelled by customer", session)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be cancelled"
        )
    
    return DataResponse(
        success=True,
        data={"message": "Order cancelled successfully"}
    )

    return DataResponse(
        success=True,
        data={"message": "Order cancelled successfully"}
    )

@router.get("/orders/{order_id}/invoice")
def get_order_invoice(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Download GST invoice PDF for the order"""
    order = session.get(CatalogOrder, order_id)
    if not order or (order.user_id != current_user.id and not current_user.is_superuser):
        raise HTTPException(status_code=404, detail="Order not found")
        
    buffer = InvoiceService.generate_order_invoice(order_id, session)
    if not buffer:
        raise HTTPException(status_code=500, detail="Failed to generate invoice")
        
    return StreamingResponse(
        buffer, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{order.order_number}.pdf"}
    )

@router.post("/orders/{order_id}/return", response_model=DataResponse[dict])
def initiate_order_return(
    order_id: int,
    request: OrderReturnRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Initiate return request for a purchased battery"""
    order = session.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
        
    success = OrderService.initiate_return(order_id, request.reason, session)
    if not success:
        raise HTTPException(status_code=400, detail="Order is not eligible for return")
        
    return DataResponse(success=True, data={"message": "Return request submitted"})

@router.get("/orders/{order_id}/tracking", response_model=DataResponse[dict])
def get_order_tracking(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Get delivery tracking for order"""
    from app.models.catalog import DeliveryTracking, DeliveryEvent
    from sqlmodel import select
    
    order = session.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    tracking = session.exec(
        select(DeliveryTracking).where(DeliveryTracking.order_id == order_id)
    ).first()
    
    if not tracking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking information not available"
        )
    
    # Get delivery events
    events = session.exec(
        select(DeliveryEvent)
        .where(DeliveryEvent.tracking_id == tracking.id)
        .order_by(DeliveryEvent.timestamp.desc())
    ).all()
    
    return DataResponse(
        success=True,
        data={
            "tracking_number": tracking.tracking_number,
            "courier_name": tracking.courier_name,
            "current_status": tracking.current_status,
            "current_location": tracking.current_location,
            "estimated_delivery_date": tracking.estimated_delivery_date.isoformat() if tracking.estimated_delivery_date else None,
            "events": [
                {
                    "status": event.status,
                    "location": event.location,
                    "description": event.description,
                    "timestamp": event.timestamp.isoformat()
                }
                for event in events
            ]
        }
    )

# --- CART MANAGEMENT ---
class CartItemUpdate(BaseModel):
    quantity: int

@router.patch("/cart/{item_id}")
async def update_cart_item(
    item_id: int,
    update: CartItemUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Update cart item quantity"""
    return {"message": "Cart item updated", "item_id": item_id, "quantity": update.quantity}

@router.delete("/cart/{item_id}")
async def remove_cart_item(
    item_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Remove item from cart"""
    return {"message": "Item removed from cart", "item_id": item_id}

# --- WARRANTY ---
class WarrantyClaimRequest(BaseModel):
    issue_description: str
    images: Optional[List[str]] = None

@router.post("/orders/{order_id}/warranty")
async def claim_warranty(
    order_id: int,
    claim: WarrantyClaimRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Claim warranty for an order"""
    order = db.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    
    from app.models.support import SupportTicket
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=f"Warranty Claim - Order #{order_id}",
        description=claim.issue_description,
        category="warranty",
        priority="medium",
        status="open"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    return {"message": "Warranty claim submitted", "ticket_id": ticket.id, "status": "under_review"}
