"""
Wezu Battery — Production Data Seeder
Seeds all critical tables that must be populated for apps to work together.
Idempotent: safe to run multiple times.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, UTC, timedelta
from sqlalchemy import text
from app.db.session import SessionLocal
import random

db = SessionLocal()

def seed_permissions():
    """Seed all permission slugs used by the RBAC system."""
    PERMISSIONS = [
        # Station
        ("station:read", "station", "Station", "read", "global", "View all stations"),
        ("station:create", "station", "Station", "create", "global", "Create stations"),
        ("station:update", "station", "Station", "update", "global", "Update stations"),
        ("station:delete", "station", "Station", "delete", "global", "Delete stations"),
        ("station:manage", "station", "Station", "manage", "global", "Full station management"),
        # Battery
        ("battery:read", "battery", "Battery", "read", "global", "View all batteries"),
        ("battery:create", "battery", "Battery", "create", "global", "Create batteries"),
        ("battery:update", "battery", "Battery", "update", "global", "Update batteries"),
        ("battery:delete", "battery", "Battery", "delete", "global", "Delete batteries"),
        ("battery:manage", "battery", "Battery", "manage", "global", "Full battery management"),
        # User
        ("user:read", "user", "User", "read", "global", "View all users"),
        ("user:create", "user", "User", "create", "global", "Create users"),
        ("user:update", "user", "User", "update", "global", "Update users"),
        ("user:delete", "user", "User", "delete", "global", "Delete users"),
        ("user:manage", "user", "User", "manage", "global", "Full user management"),
        # Dealer
        ("dealer:read", "dealer", "Dealer", "read", "global", "View all dealers"),
        ("dealer:create", "dealer", "Dealer", "create", "global", "Create dealers"),
        ("dealer:update", "dealer", "Dealer", "update", "global", "Update dealers"),
        ("dealer:delete", "dealer", "Dealer", "delete", "global", "Delete dealers"),
        ("dealer:approve", "dealer", "Dealer", "approve", "global", "Approve dealer applications"),
        ("dealer:manage", "dealer", "Dealer", "manage", "global", "Full dealer management"),
        # Rental
        ("rental:read", "rental", "Rental", "read", "global", "View rentals"),
        ("rental:create", "rental", "Rental", "create", "global", "Create rentals"),
        ("rental:update", "rental", "Rental", "update", "global", "Update rentals"),
        ("rental:manage", "rental", "Rental", "manage", "global", "Full rental management"),
        # Analytics
        ("analytics:read", "analytics", "Analytics", "read", "global", "View analytics"),
        ("analytics:export", "analytics", "Analytics", "export", "global", "Export analytics data"),
        # Finance
        ("finance:read", "finance", "Finance", "read", "global", "View financial reports"),
        ("finance:manage", "finance", "Finance", "manage", "global", "Manage financial settings"),
        ("commission:read", "commission", "Commission", "read", "global", "View commissions"),
        ("commission:manage", "commission", "Commission", "manage", "global", "Manage commission configs"),
        ("settlement:read", "settlement", "Settlement", "read", "global", "View settlements"),
        ("settlement:manage", "settlement", "Settlement", "manage", "global", "Manage settlements"),
        # Support
        ("support:read", "support", "Support", "read", "global", "View support tickets"),
        ("support:manage", "support", "Support", "manage", "global", "Manage support tickets"),
        # Inventory
        ("inventory:read", "inventory", "Inventory", "read", "global", "View inventory"),
        ("inventory:manage", "inventory", "Inventory", "manage", "global", "Manage inventory"),
        # Logistics
        ("logistics:read", "logistics", "Logistics", "read", "global", "View logistics"),
        ("logistics:manage", "logistics", "Logistics", "manage", "global", "Manage logistics"),
        # KYC
        ("kyc:read", "kyc", "KYC", "read", "global", "View KYC documents"),
        ("kyc:verify", "kyc", "KYC", "verify", "global", "Verify KYC documents"),
        ("kyc:manage", "kyc", "KYC", "manage", "global", "Full KYC management"),
        # Notification
        ("notification:read", "notification", "Notification", "read", "global", "View notifications"),
        ("notification:send", "notification", "Notification", "send", "global", "Send notifications"),
        ("notification:manage", "notification", "Notification", "manage", "global", "Manage notification configs"),
        # Audit
        ("audit:read", "audit", "AuditLog", "read", "global", "View audit logs"),
        # RBAC
        ("rbac:read", "rbac", "RBAC", "read", "global", "View roles & permissions"),
        ("rbac:manage", "rbac", "RBAC", "manage", "global", "Manage roles & permissions"),
        # CMS
        ("cms:read", "cms", "CMS", "read", "global", "View CMS content"),
        ("cms:manage", "cms", "CMS", "manage", "global", "Manage CMS content"),
        # System
        ("system:config", "system", "System", "config", "global", "System configuration"),
        ("system:maintenance", "system", "System", "maintenance", "global", "System maintenance mode"),
    ]
    
    existing = {r[0] for r in db.execute(text("SELECT slug FROM permissions")).fetchall()}
    count = 0
    for slug, module, resource_type, action, scope, desc in PERMISSIONS:
        if slug not in existing:
            db.execute(text("""
                INSERT INTO permissions (slug, module, resource_type, action, scope, description)
                VALUES (:slug, :module, :rt, :action, :scope, :desc)
            """), {"slug": slug, "module": module, "rt": resource_type, "action": action, "scope": scope, "desc": desc})
            count += 1
    db.commit()
    print(f"✅ Permissions: {count} new (total {len(PERMISSIONS)})")

def seed_role_permissions():
    """Assign permissions to roles based on their purpose."""
    # Role ID → list of permission slug prefixes they get
    ROLE_PERMS = {
        30: ["*"],  # admin → ALL permissions
        31: ["rental:read", "support:read", "notification:read"],  # customer
        32: ["station:read", "battery:read", "rental:read", "inventory:read",
             "analytics:read", "commission:read", "support:read", "notification:read"],  # dealer
        33: ["station:read", "station:update", "battery:read", "battery:update",
             "inventory:read", "inventory:manage"],  # station_manager
        34: ["station:read", "battery:read", "battery:update",
             "inventory:read"],  # technician
        35: ["logistics:read", "logistics:manage", "inventory:read"],  # logistics_manager
        36: ["logistics:read"],  # driver
        37: ["inventory:read", "inventory:manage", "battery:read"],  # warehouse_manager
        38: ["support:read", "support:manage", "user:read"],  # support_agent
        39: ["finance:read", "finance:manage", "commission:read", "commission:manage",
             "settlement:read", "settlement:manage", "analytics:read"],  # finance_manager
        40: ["kyc:read", "kyc:verify", "dealer:read"],  # inspector
        41: ["station:read", "station:manage", "dealer:read", "analytics:read",
             "inventory:read", "support:read"],  # franchise_owner
        42: ["analytics:read", "cms:read", "cms:manage", "notification:send"],  # marketing_manager
        43: ["analytics:read", "analytics:export"],  # analyst
    }
    
    all_perms = {r[0]: r[1] for r in db.execute(text("SELECT slug, id FROM permissions")).fetchall()}
    existing = {(r[0], r[1]) for r in db.execute(text("SELECT role_id, permission_id FROM role_permissions")).fetchall()}
    
    count = 0
    for role_id, prefixes in ROLE_PERMS.items():
        for perm_slug, perm_id in all_perms.items():
            should_assign = False
            if "*" in prefixes:
                should_assign = True
            else:
                for prefix in prefixes:
                    if perm_slug == prefix or perm_slug.startswith(prefix.rstrip(":") + ":"):
                        should_assign = True
                        break
            
            if should_assign and (role_id, perm_id) not in existing:
                db.execute(text("""
                    INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)
                """), {"rid": role_id, "pid": perm_id})
                count += 1
    db.commit()
    print(f"✅ Role-Permissions: {count} new assignments")

def seed_user_roles():
    """Assign users to roles via the user_roles M2M table (mirrors their role_id FK)."""
    users = db.execute(text("SELECT id, role_id FROM users WHERE role_id IS NOT NULL")).fetchall()
    existing = {r[0] for r in db.execute(text("SELECT user_id FROM user_roles")).fetchall()}
    
    count = 0
    for user_id, role_id in users:
        if user_id not in existing:
            db.execute(text("""
                INSERT INTO user_roles (user_id, role_id, notes, effective_from, created_at)
                VALUES (:uid, :rid, 'System assigned', NOW(), NOW())
            """), {"uid": user_id, "rid": role_id})
            count += 1
    db.commit()
    print(f"✅ User-Roles: {count} new assignments")

def seed_wallets():
    """Create wallets for all users who don't have one."""
    # Check wallet table structure first
    try:
        cols = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='wallets' ORDER BY ordinal_position")).fetchall()
        col_names = [c[0] for c in cols]
        
        users = db.execute(text("SELECT id FROM users")).fetchall()
        if 'user_id' in col_names:
            existing = {r[0] for r in db.execute(text("SELECT user_id FROM wallets")).fetchall()}
            count = 0
            for (user_id,) in users:
                if user_id not in existing:
                    db.execute(text("""
                        INSERT INTO wallets (user_id, balance, cashback_balance, currency, is_frozen, updated_at)
                        VALUES (:uid, 0.0, 0.0, 'INR', false, NOW())
                    """), {"uid": user_id})
                    count += 1
            db.commit()
            print(f"✅ Wallets: {count} new wallets created")
        else:
            print(f"⚠️  Wallets: table structure doesn't have user_id column. Columns: {col_names}")
    except Exception as e:
        print(f"⚠️  Wallets: skipped ({e})")
        db.rollback()

def seed_reviews():
    """Add sample reviews to stations that don't have any."""
    existing_count = db.execute(text("SELECT count(*) FROM reviews")).fetchone()[0]
    if existing_count > 0:
        print(f"⚠️  Reviews: already {existing_count} reviews, skipping")
        return
    
    stations = db.execute(text("SELECT id FROM stations")).fetchall()
    customers = db.execute(text("SELECT id FROM users WHERE user_type = 'CUSTOMER'")).fetchall()
    customer_ids = [c[0] for c in customers]
    
    if not customer_ids:
        print("⚠️  Reviews: no customers found, skipping")
        return
    
    REVIEW_TEXTS = [
        (5, "Excellent station! Fast battery swap and friendly staff. Highly recommended."),
        (4, "Good experience overall. Sometimes there's a wait but batteries are always well-charged."),
        (5, "Best battery swap station in the area. Clean facility and quick service."),
        (4, "Reliable service. Battery quality is consistently good. Will visit again."),
        (3, "Decent station but could improve wait times during peak hours."),
        (5, "Super convenient location. The app integration makes it very easy to use."),
        (4, "Great battery quality. Parking could be better near the station."),
        (4, "Been using this station for 3 months now. Very satisfied with the service."),
        (5, "Perfect for daily commute. Never had a bad battery here."),
        (3, "Average experience. Staff were helpful but the process was a bit slow."),
    ]
    
    # Check reviews table columns
    cols = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='reviews' ORDER BY ordinal_position")).fetchall()
    col_names = [c[0] for c in cols]
    
    count = 0
    for (station_id,) in stations:
        num_reviews = random.randint(3, 5)
        used_customers = set()
        for i in range(num_reviews):
            customer_id = random.choice(customer_ids)
            while customer_id in used_customers and len(used_customers) < len(customer_ids):
                customer_id = random.choice(customer_ids)
            used_customers.add(customer_id)
            
            rating, comment = random.choice(REVIEW_TEXTS)
            days_ago = random.randint(1, 90)
            
            try:
                if 'comment' in col_names:
                    db.execute(text("""
                        INSERT INTO reviews (user_id, station_id, rating, comment, created_at, is_verified_rental, is_hidden, helpful_count)
                        VALUES (:uid, :sid, :rating, :comment, :created, false, false, 0)
                    """), {
                        "uid": customer_id, "sid": station_id,
                        "rating": rating, "comment": comment,
                        "created": datetime.now(UTC) - timedelta(days=days_ago)
                    })
                elif 'content' in col_names:
                    db.execute(text("""
                        INSERT INTO reviews (user_id, station_id, rating, content, created_at, is_verified_rental, is_hidden, helpful_count)
                        VALUES (:uid, :sid, :rating, :content, :created, false, false, 0)
                    """), {
                        "uid": customer_id, "sid": station_id,
                        "rating": rating, "content": comment,
                        "created": datetime.now(UTC) - timedelta(days=days_ago)
                    })
                count += 1
            except Exception as e:
                db.rollback()
                print(f"⚠️  Reviews: error inserting ({e})")
                return
    db.commit()
    print(f"✅ Reviews: {count} new reviews")

def seed_commission_configs():
    """Create default commission configs for dealers."""
    existing = db.execute(text("SELECT count(*) FROM commission_configs")).fetchone()[0]
    if existing > 0:
        print(f"⚠️  Commission configs: already {existing}, skipping")
        return
    
    dealers = db.execute(text("SELECT dp.id, dp.user_id FROM dealer_profiles dp")).fetchall()
    count = 0
    for dealer_profile_id, user_id in dealers:
        for txn_type, pct, flat in [("rental", 10.0, 0.0), ("swap", 8.0, 5.0), ("purchase", 12.0, 0.0)]:
            db.execute(text("""
                INSERT INTO commission_configs (dealer_id, transaction_type, percentage, flat_fee, is_active, created_at, effective_from)
                VALUES (:did, :tt, :pct, :ff, true, NOW(), NOW())
            """), {"did": user_id, "tt": txn_type, "pct": pct, "ff": flat})
            count += 1
    db.commit()
    print(f"✅ Commission configs: {count} new configs")

def activate_stations():
    """Set station status to 'active' so they show up for customers."""
    result = db.execute(text("""
        UPDATE stations SET status = 'active', updated_at = NOW()
        WHERE status IN ('OFFLINE', 'offline')
    """))
    db.commit()
    print(f"✅ Stations: {result.rowcount} stations activated (were OFFLINE)")

def seed_station_images():
    """Add placeholder image URLs to station_images table."""
    existing = db.execute(text("SELECT count(*) FROM station_images")).fetchone()[0]
    if existing > 0:
        print(f"⚠️  Station images: already {existing}, skipping")
        return
    
    stations = db.execute(text("SELECT id FROM stations")).fetchall()
    count = 0
    for (station_id,) in stations:
        for i in range(1, 3):
            is_primary = (i == 1)
            db.execute(text("""
                INSERT INTO station_images (station_id, url, is_primary)
                VALUES (:sid, :url, :ip)
            """), {"sid": station_id, "url": f"/media/stations/station_{station_id}_{i}.jpg", "ip": is_primary})
            count += 1
    db.commit()
    print(f"✅ Station images: {count} new images")

def update_station_ratings():
    """Recalculate station ratings from reviews."""
    try:
        db.execute(text("""
            UPDATE stations s SET rating = sub.avg_rating
            FROM (
                SELECT station_id, ROUND(AVG(rating)::numeric, 1) as avg_rating
                FROM reviews
                GROUP BY station_id
            ) sub
            WHERE s.id = sub.station_id
        """))
        db.commit()
        print("✅ Station ratings: recalculated from reviews")
    except Exception as e:
        db.rollback()
        print(f"⚠️  Station ratings: skipped ({e})")

if __name__ == "__main__":
    print("🚀 Wezu Battery — Production Data Seeder")
    print("=" * 50)
    
    seed_permissions()
    seed_role_permissions()
    seed_user_roles()
    seed_wallets()
    seed_reviews()
    seed_commission_configs()
    seed_station_images()
    activate_stations()
    update_station_ratings()
    
    print("=" * 50)
    print("✅ Seeding complete!")
    
    db.close()
