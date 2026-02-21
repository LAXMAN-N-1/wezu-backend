"""
Catalog Service
CatalogProduct catalog management with search and filtering
"""
from sqlmodel import Session, select, or_, and_
from typing import List, Optional, Dict
from app.models.catalog import CatalogProduct, CatalogProductImage, CatalogProductVariant
from app.schemas.catalog import ProductCreate, ProductUpdate
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CatalogService:
    """CatalogProduct catalog management"""
    
    @staticmethod
    def search_products(
        query: Optional[str],
        category: Optional[str],
        brand: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        min_capacity: Optional[int],
        max_capacity: Optional[int],
        min_rating: Optional[float],
        in_stock_only: bool,
        sort_by: str,
        limit: int,
        offset: int,
        session: Session
    ) -> tuple[List[CatalogProduct], int]:
        """
        Search and filter products
        
        Returns:
            Tuple of (products, total_count)
        """
        # Base query
        query_stmt = select(CatalogProduct).where(CatalogProduct.status == "ACTIVE")
        
        # Text search
        if query:
            query_stmt = query_stmt.where(
                or_(
                    CatalogProduct.name.ilike(f"%{query}%"),
                    CatalogProduct.description.ilike(f"%{query}%"),
                    CatalogProduct.brand.ilike(f"%{query}%"),
                    CatalogProduct.tags.ilike(f"%{query}%")
                )
            )
        
        # Category filter
        if category:
            query_stmt = query_stmt.where(CatalogProduct.category == category)
        
        # Brand filter
        if brand:
            query_stmt = query_stmt.where(CatalogProduct.brand == brand)
        
        # Price range
        if min_price is not None:
            query_stmt = query_stmt.where(CatalogProduct.price >= min_price)
        if max_price is not None:
            query_stmt = query_stmt.where(CatalogProduct.price <= max_price)
        
        # Capacity range (for batteries)
        if min_capacity is not None:
            query_stmt = query_stmt.where(CatalogProduct.capacity_mah >= min_capacity)
        if max_capacity is not None:
            query_stmt = query_stmt.where(CatalogProduct.capacity_mah <= max_capacity)
        
        # Rating filter
        if min_rating is not None:
            query_stmt = query_stmt.where(CatalogProduct.average_rating >= min_rating)
        
        # Stock filter
        if in_stock_only:
            query_stmt = query_stmt.where(CatalogProduct.stock_quantity > 0)
        
        # Get total count
        total_count = len(session.exec(query_stmt).all())
        
        # Sorting
        if sort_by == "price_asc":
            query_stmt = query_stmt.order_by(CatalogProduct.price.asc())
        elif sort_by == "price_desc":
            query_stmt = query_stmt.order_by(CatalogProduct.price.desc())
        elif sort_by == "rating":
            query_stmt = query_stmt.order_by(CatalogProduct.average_rating.desc())
        elif sort_by == "popularity":
            query_stmt = query_stmt.order_by(CatalogProduct.review_count.desc())
        elif sort_by == "newest":
            query_stmt = query_stmt.order_by(CatalogProduct.created_at.desc())
        else:  # Default: featured first, then newest
            query_stmt = query_stmt.order_by(
                CatalogProduct.is_featured.desc(),
                CatalogProduct.created_at.desc()
            )
        
        # Pagination
        query_stmt = query_stmt.offset(offset).limit(limit)
        
        products = session.exec(query_stmt).all()
        
        return products, total_count
    
    @staticmethod
    def get_product_details(product_id: int, session: Session) -> Optional[Dict]:
        """Get complete product details with images and variants"""
        product = session.get(CatalogProduct, product_id)
        if not product:
            return None
        
        # Get images
        images = session.exec(
            select(CatalogProductImage)
            .where(CatalogProductImage.product_id == product_id)
            .order_by(CatalogProductImage.display_order)
        ).all()
        
        # Get variants
        variants = session.exec(
            select(CatalogProductVariant)
            .where(CatalogProductVariant.product_id == product_id)
            .where(CatalogProductVariant.is_active == True)
        ).all()
        
        return {
            "product": product,
            "images": images,
            "variants": variants,
            "in_stock": product.stock_quantity > 0 or any(v.stock_quantity > 0 for v in variants)
        }
    
    @staticmethod
    def get_featured_products(limit: int, session: Session) -> List[CatalogProduct]:
        """Get featured products"""
        return session.exec(
            select(CatalogProduct)
            .where(CatalogProduct.is_featured == True)
            .where(CatalogProduct.status == "ACTIVE")
            .order_by(CatalogProduct.created_at.desc())
            .limit(limit)
        ).all()
    
    @staticmethod
    def get_bestsellers(limit: int, session: Session) -> List[CatalogProduct]:
        """Get bestseller products"""
        return session.exec(
            select(CatalogProduct)
            .where(CatalogProduct.is_bestseller == True)
            .where(CatalogProduct.status == "ACTIVE")
            .order_by(CatalogProduct.review_count.desc())
            .limit(limit)
        ).all()
    
    @staticmethod
    def check_stock_availability(
        product_id: int,
        variant_id: Optional[int],
        quantity: int,
        session: Session
    ) -> bool:
        """Check if product/variant has sufficient stock"""
        if variant_id:
            variant = session.get(CatalogProductVariant, variant_id)
            return variant and variant.stock_quantity >= quantity
        else:
            product = session.get(CatalogProduct, product_id)
            return product and product.stock_quantity >= quantity
    
    @staticmethod
    def reserve_stock(
        product_id: int,
        variant_id: Optional[int],
        quantity: int,
        session: Session
    ) -> bool:
        """Reserve stock for order (decrease stock quantity)"""
        try:
            if variant_id:
                variant = session.get(CatalogProductVariant, variant_id)
                if not variant or variant.stock_quantity < quantity:
                    return False
                variant.stock_quantity -= quantity
                session.add(variant)
            else:
                product = session.get(CatalogProduct, product_id)
                if not product or product.stock_quantity < quantity:
                    return False
                product.stock_quantity -= quantity
                session.add(product)
            
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to reserve stock: {str(e)}")
            return False
    
    @staticmethod
    def release_stock(
        product_id: int,
        variant_id: Optional[int],
        quantity: int,
        session: Session
    ):
        """Release reserved stock (increase stock quantity)"""
        try:
            if variant_id:
                variant = session.get(CatalogProductVariant, variant_id)
                if variant:
                    variant.stock_quantity += quantity
                    session.add(variant)
            else:
                product = session.get(CatalogProduct, product_id)
                if product:
                    product.stock_quantity += quantity
                    session.add(product)
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to release stock: {str(e)}")
    @staticmethod
    def get_catalog_metadata(session: Session) -> Dict[str, Any]:
        """Get available categories, brands, and price ranges for filtering"""
        from sqlmodel import func
        
        categories = session.exec(select(CatalogProduct.category).distinct()).all()
        brands = session.exec(select(CatalogProduct.brand).distinct()).all()
        
        # Price range
        min_price = session.exec(select(func.min(CatalogProduct.price))).one() or 0
        max_price = session.exec(select(func.max(CatalogProduct.price))).one() or 0
        
        # Capacities (for battery filtering)
        capacities = session.exec(
            select(CatalogProduct.capacity_mah)
            .where(CatalogProduct.category == "BATTERY")
            .distinct()
        ).all()
        
        return {
            "categories": [c for c in categories if c],
            "brands": [b for b in brands if b],
            "price_range": {"min": min_price, "max": max_price},
            "capacities": [cap for cap in capacities if cap]
        }

    @staticmethod
    def create_product(product_in: ProductCreate, session: Session) -> CatalogProduct:
        """Admin: Create new product and associated images/variants"""
        data = product_in.model_dump(exclude={"images", "variants"})
        product = CatalogProduct(**data)
        session.add(product)
        session.flush()
        
        # Add images
        for img_in in product_in.images:
            image = CatalogProductImage(product_id=product.id, **img_in.model_dump())
            session.add(image)
            
        # Add variants
        for var_in in product_in.variants:
            variant = CatalogProductVariant(product_id=product.id, **var_in.model_dump())
            session.add(variant)
            
        session.commit()
        session.refresh(product)
        return product

    @staticmethod
    def update_product(product_id: int, product_in: ProductUpdate, session: Session) -> Optional[CatalogProduct]:
        """Admin: Update product details"""
        product = session.get(CatalogProduct, product_id)
        if not product:
            return None
            
        update_data = product_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
            
        product.updated_at = datetime.utcnow()
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    @staticmethod
    def delete_product(product_id: int, session: Session) -> bool:
        """Admin: Deactivate product"""
        product = session.get(CatalogProduct, product_id)
        if not product:
            return False
            
        product.status = "INACTIVE"
        product.updated_at = datetime.utcnow()
        session.add(product)
        session.commit()
        return True
