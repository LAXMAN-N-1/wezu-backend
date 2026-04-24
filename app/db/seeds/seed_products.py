from __future__ import annotations
import os
from sqlmodel import Session, create_engine, select
from app.models.catalog import CatalogProduct, CatalogProductImage, ProductCategory, ProductStatus
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def seed_products():
    products = [
        {
            "name": "Wezu EV Battery",
            "description": "High-performance lithium-ion battery for electric vehicles.",
            "category": "BATTERY",
            "brand": "Wezu",
            "model": "EV-1000",
            "sku": "BATT-EV-1000",
            "price": 24999.0,
            "original_price": 29999.0,
            "discount_percentage": 16.6,
            "capacity_mah": 50000,
            "voltage": 72.0,
            "stock_quantity": 50,
            "is_featured": True,
            "is_bestseller": True,
            "image": "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=500"
        },
        {
            "name": "Smart Home Solar Hub",
            "description": "Complete energy storage solution for smart homes.",
            "category": "BUNDLE",
            "brand": "Wezu",
            "model": "SH-2000",
            "sku": "HUB-SH-2000",
            "price": 45000.0,
            "original_price": 50000.0,
            "discount_percentage": 10.0,
            "capacity_mah": 100000,
            "voltage": 220.0,
            "stock_quantity": 20,
            "is_featured": True,
            "is_bestseller": False,
            "image": "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?w=500"
        },
        {
            "name": "Fast Charger Pro",
            "description": "72V Fast charger for EV batteries.",
            "category": "CHARGER",
            "brand": "Wezu",
            "model": "FC-Pro",
            "sku": "CHG-FC-PRO",
            "price": 3499.0,
            "stock_quantity": 100,
            "is_featured": False,
            "is_bestseller": True,
            "image": "https://images.unsplash.com/photo-1584820927500-b63ff39dce0a?w=500"
        },
        {
            "name": "Standard Inverter",
            "description": "Reliable 1KVA inverter for home backup.",
            "category": "ACCESSORY",
            "brand": "Wezu",
            "model": "INV-1K",
            "sku": "INV-1000",
            "price": 8500.0,
            "stock_quantity": 30,
            "is_featured": False,
            "is_bestseller": False,
            "image": "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?w=500"
        }
    ]

    with Session(engine) as session:
        has_products = session.exec(select(CatalogProduct)).first()
        if has_products:
            print("Products already seeded.")
            return

        for p in products:
            img_url = p.pop("image")
            product = CatalogProduct(**p, status=ProductStatus.ACTIVE)
            session.add(product)
            session.commit()
            session.refresh(product)
            
            # Add image
            image = CatalogProductImage(
                product_id=product.id,
                image_url=img_url,
                alt_text=product.name,
                is_primary=True
            )
            session.add(image)
        
        session.commit()
        print("Successfully seeded products!")

if __name__ == "__main__":
    seed_products()
