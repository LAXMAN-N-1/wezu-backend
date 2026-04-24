from __future__ import annotations
from sqlmodel import Session, select
from app.models.ecommerce import EcommerceProduct, EcommerceOrder, EcommerceOrderItem
from app.models.user import User
from fastapi import HTTPException
from typing import List, Optional

class ProductService:
    @staticmethod
    def get_all_products(db: Session, category: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[EcommerceProduct]:
        query = select(EcommerceProduct).where(EcommerceProduct.is_active == True)
        if category:
            query = query.where(EcommerceProduct.category == category)
        return db.exec(query.offset(skip).limit(limit)).all()

    @staticmethod
    def get_product(db: Session, product_id: int) -> EcommerceProduct:
        product = db.get(EcommerceProduct, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="EcommerceProduct not found")
        return product

    @staticmethod
    def create_product(db: Session, product_data: EcommerceProduct) -> EcommerceProduct:
        db.add(product_data)
        db.commit()
        db.refresh(product_data)
        return product_data

class OrderService:
    @staticmethod
    def create_order(db: Session, user_id: int, items_data: List[dict], shipping_address_id: int) -> EcommerceOrder:
        total_amount = 0.0
        order_items = []
        
        # Batch-load all products at once (eliminates per-item db.get N+1)
        product_ids = [item["product_id"] for item in items_data]
        products = db.exec(select(EcommerceProduct).where(EcommerceProduct.id.in_(product_ids))).all()
        products_map = {p.id: p for p in products}

        for item in items_data:
            product = products_map.get(item["product_id"])
            if not product:
                raise HTTPException(status_code=404, detail=f"EcommerceProduct {item['product_id']} not found")
            if product.stock_quantity < item["quantity"]:
                 raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")
            
            # Update stock
            product.stock_quantity -= item["quantity"]
            db.add(product)
            
            # Calculate price
            line_total = product.price * item["quantity"]
            total_amount += line_total
            
            order_items.append(EcommerceOrderItem(
                product_id=product.id,
                quantity=item["quantity"],
                unit_price=product.price,
                total_price=line_total
            ))
            
        # Create Order
        order = EcommerceOrder(
            user_id=user_id,
            total_amount=total_amount,
            status="pending",
            shipping_address_id=shipping_address_id
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        
        # Add Items
        for oi in order_items:
            oi.order_id = order.id
            db.add(oi)
            
        db.commit()
        db.refresh(order)
        return order
