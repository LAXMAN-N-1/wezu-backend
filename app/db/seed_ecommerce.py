from sqlmodel import Session, select
from app.db.session import engine
from app.models.catalog import CatalogProduct, CatalogProductImage, CatalogProductVariant
# Explicitly import models to ensure SQLModel registry is populated
from app.models.user import User
from app.models.staff import StaffProfile
from app.models.session import UserSession
import app.models # Warm up registry
from datetime import datetime
import random

def seed_ecommerce():
    with Session(engine) as session:
        # Check if already seeded
        existing = session.exec(select(CatalogProduct)).first()
        if existing:
            print("Ecommerce catalog already seeded.")
            return

        brands = ["Wezu Pro", "EcoCell", "VoltMax", "PowerFlow", "ThunderVolt"]
        types = ["Li-Ion", "LiFePO4", "Solid State"]
        capacities = [2000, 3000, 5000, 7500, 10000]
        colors = ["Midnight Black", "Arctic Silver", "Pearl White", "Safe Blue", "Eco Green"]
        base_prices = {
            2000: 499,
            3000: 799,
            5000: 1299,
            7500: 1899,
            10000: 2499
        }

        products_to_seed = []
        
        # We need 50+ products. 5 brands * 3 types * 4 capacities = 60 products
        for brand in brands:
            for b_type in types:
                for capacity in capacities[:4]: # 4 capacities per brand/type combo
                    name = f"{brand} {b_type} {capacity}mAh"
                    model = f"{brand[:2].upper()}-{random.randint(100, 999)}"
                    sku = f"WEZU-B-{brand[:3].upper()}-{random.randint(1000, 9999)}"
                    
                    price = base_prices.get(capacity, 1000) + random.randint(-50, 200)
                    
                    product = CatalogProduct(
                        name=name,
                        description=f"High-quality {b_type} battery by {brand} with {capacity}mAh capacity. Optimized for long life and fast charging.",
                        category="BATTERY",
                        brand=brand,
                        model=model,
                        sku=sku,
                        price=price,
                        original_price=price + 200,
                        discount_percentage=15,
                        capacity_mah=capacity,
                        voltage=3.7 if b_type == "Li-Ion" else 3.2,
                        battery_type=b_type,
                        warranty_months=random.choice([12, 24, 36]),
                        stock_quantity=random.randint(10, 100),
                        average_rating=round(random.uniform(4.0, 5.0), 1),
                        review_count=random.randint(50, 500),
                        status="ACTIVE",
                        is_featured=random.choice([True, False, False]),
                    )
                    session.add(product)
                    products_to_seed.append(product)

        session.commit()
        
        # Add images and variants
        for product in products_to_seed:
            session.refresh(product)
            
            # Add images
            img_urls = [
                "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=600",
                "https://images.unsplash.com/photo-1611333162391-76bcbf042431?w=600"
            ]
            for i, url in enumerate(img_urls):
                img = CatalogProductImage(
                    product_id=product.id,
                    image_url=url,
                    alt_text=f"{product.name} Image {i+1}",
                    display_order=i,
                    is_primary=(i == 0)
                )
                session.add(img)
            
            # Add variants (e.g., Color variants)
            for color in colors[:3]:
                variant_sku = f"{product.sku}-{color[:3].upper()}"
                variant = CatalogProductVariant(
                    product_id=product.id,
                    variant_name=f"{color}",
                    sku=variant_sku,
                    price=product.price + random.randint(0, 50),
                    stock_quantity=random.randint(5, 20),
                    color=color,
                    capacity_mah=product.capacity_mah
                )
                session.add(variant)
        
        session.commit()
        print(f"Successfully seeded {len(products_to_seed)} products with images and variants.")

if __name__ == "__main__":
    seed_ecommerce()
