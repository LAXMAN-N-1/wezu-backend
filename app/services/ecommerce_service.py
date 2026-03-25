from sqlmodel import Session, select, col
from app.models.ecommerce import EcommerceProduct, EcommerceOrder, EcommerceOrderItem
from app.models.user import User
from fastapi import HTTPException
from typing import List, Optional

class ProductService:
    @staticmethod
    def get_all_products(db: Session, category: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[EcommerceProduct]:
        query = select(EcommerceProduct).where(col(EcommerceProduct.is_active) == True)
        if category:
            query = query.where(col(EcommerceProduct.category) == category)
        return list(db.exec(query.offset(skip).limit(limit)).all())

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
        prepared_items = []
        
        for item in items_data:
            product = db.get(EcommerceProduct, item["product_id"])
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
            
            assert product.id is not None
            prepared_items.append({
                "product_id": product.id,
                "quantity": item["quantity"],
                "unit_price": product.price,
                "total_price": line_total
            })
            
        # Create Order
        order = EcommerceOrder(
            user_id=user_id,
            total_amount=total_amount,
            status="pending",
            shipping_address_id=shipping_address_id
        )
        db.add(order)
        db.flush()
        assert order.id is not None
        
        # Add Items
        for item_info in prepared_items:
            oi = EcommerceOrderItem(
                order_id=order.id,
                **item_info
            )
            db.add(oi)
            
        db.commit()
        db.refresh(order)
        return order
