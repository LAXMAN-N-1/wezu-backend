"""
Master seed script for Admin Portal screens.
Seeds: audit_logs, maintenance_records, dealer_profiles, dealer_applications,
       dealer_documents, commission_configs, rentals, swaps, purchases, late_fees
"""
import sys, os, random, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select, text
from app.core.database import engine

# ─── Helpers ───
def rand_date(days_back=90):
    return datetime.now(UTC) - timedelta(days=random.randint(0, days_back), hours=random.randint(0,23), minutes=random.randint(0,59))

def ensure_table(conn, table_name):
    result = conn.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"), {"t": table_name}).scalar()
    return result

def seed_audit_trails(conn):
    if not ensure_table(conn, "inventory_audit_logs"):
        print("⚠ inventory_audit_logs table missing, creating...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory_audit_logs (
                id SERIAL PRIMARY KEY,
                battery_id INTEGER,
                action_type VARCHAR NOT NULL,
                from_location_type VARCHAR,
                from_location_id INTEGER,
                to_location_type VARCHAR,
                to_location_id INTEGER,
                actor_id INTEGER,
                notes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    existing = conn.execute(text("SELECT COUNT(*) FROM inventory_audit_logs")).scalar()
    if existing > 5:
        print(f"  ✓ inventory_audit_logs already has {existing} rows, skipping")
        return

    action_types = ["transfer", "status_change", "manual_entry", "disposal", "restock", "reassignment"]
    loc_types = ["warehouse", "station", "service_center"]
    notes_pool = [
        "Routine transfer between locations",
        "Battery flagged for maintenance",
        "Manual stock correction after audit",
        "Battery disposed - end of life cycle",
        "Restocked from supplier shipment",
        "Reassigned due to demand spike",
        "Quarterly inventory reconciliation",
        "Emergency transfer for low-stock station",
        "Battery returned from customer",
        "Pre-deployment quality check passed",
    ]

    for i in range(60):
        action = random.choice(action_types)
        conn.execute(text("""
            INSERT INTO inventory_audit_logs (battery_id, action_type, from_location_type, from_location_id, to_location_type, to_location_id, actor_id, notes, timestamp)
            VALUES (:bid, :action, :flt, :fli, :tlt, :tli, :aid, :notes, :ts)
        """), {
            "bid": random.randint(1, 50),
            "action": action,
            "flt": random.choice(loc_types) if action == "transfer" else None,
            "fli": random.randint(1, 10) if action == "transfer" else None,
            "tlt": random.choice(loc_types) if action in ("transfer", "restock") else None,
            "tli": random.randint(1, 10) if action in ("transfer", "restock") else None,
            "aid": 1,
            "notes": random.choice(notes_pool),
            "ts": rand_date(120).isoformat(),
        })
    conn.commit()
    print("  ✓ Seeded 60 inventory_audit_logs")


def seed_maintenance(conn):
    if not ensure_table(conn, "maintenance_records"):
        print("⚠ maintenance_records table missing, creating...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS maintenance_records (
                id SERIAL PRIMARY KEY,
                entity_type VARCHAR NOT NULL,
                entity_id INTEGER NOT NULL,
                technician_id INTEGER NOT NULL,
                maintenance_type VARCHAR NOT NULL,
                description TEXT NOT NULL,
                cost FLOAT DEFAULT 0.0,
                parts_replaced TEXT,
                status VARCHAR DEFAULT 'completed',
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    existing = conn.execute(text("SELECT COUNT(*) FROM maintenance_records")).scalar()
    if existing > 5:
        print(f"  ✓ maintenance_records already has {existing} rows, skipping")
        return

    descriptions = [
        "Slot connector replacement and calibration",
        "Power supply unit inspection and firmware update",
        "Full station cleaning and sanitization",
        "Battery bay temperature sensor replacement",
        "UPS backup battery replacement",
        "Network module reconfiguration",
        "Emergency fire suppression system test",
        "Charging circuit board repair",
        "LCD status display replacement",
        "Monthly preventive maintenance check",
        "Weatherproofing seal replacement",
        "Security camera and lock mechanism service",
    ]
    parts_pool = [
        '["Connector Module CM-X1", "Wiring Harness WH-12"]',
        '["Power Supply PS-500W", "Fuse Block FB-30A"]',
        '["Temperature Sensor TS-200", "Thermal Paste TP-5g"]',
        '["UPS Battery 12V-7Ah", "Voltage Regulator VR-24"]',
        '["Network Card NC-WiFi6", "Ethernet Cable CAT6"]',
        None, None, None,
    ]
    statuses = ["scheduled", "in_progress", "completed", "completed", "completed"]

    station_ids = conn.execute(text("SELECT id FROM stations LIMIT 10")).fetchall()
    sids = [r[0] for r in station_ids] if station_ids else [1, 2, 3]

    for i in range(25):
        status = random.choice(statuses)
        conn.execute(text("""
            INSERT INTO maintenance_records (entity_type, entity_id, technician_id, maintenance_type, description, cost, parts_replaced, status, performed_at)
            VALUES ('station', :eid, 1, :mtype, :desc, :cost, :parts, :status, :ts)
        """), {
            "eid": random.choice(sids),
            "mtype": random.choice(["preventive", "corrective"]),
            "desc": random.choice(descriptions),
            "cost": round(random.uniform(500, 15000), 2),
            "parts": random.choice(parts_pool),
            "status": status,
            "ts": rand_date(90).isoformat(),
        })
    conn.commit()
    print("  ✓ Seeded 25 maintenance_records")


def seed_dealers(conn):
    if not ensure_table(conn, "dealer_profiles"):
        print("⚠ dealer_profiles table missing, skipping dealer seed")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM dealer_profiles")).scalar()
    if existing > 3:
        print(f"  ✓ dealer_profiles already has {existing} rows, skipping")
        return

    dealers = [
        ("GreenVolt Motors", "Hyderabad", "Telangana", "500001", "Ravi Kumar", "ravi@greenvolt.in", "+91-9876543210", "12 Banjara Hills Rd", "29ABCDE1234F1Z5", "ABCDE1234F"),
        ("EcoPower Solutions", "Bangalore", "Karnataka", "560001", "Priya Sharma", "priya@ecopower.in", "+91-9876543211", "45 MG Road", "29FGHIJ5678G2Y6", "FGHIJ5678G"),
        ("VoltEdge Dealers", "Chennai", "Tamil Nadu", "600001", "Arun Patel", "arun@voltedge.in", "+91-9876543212", "78 Anna Nagar", "33KLMNO9012H3X7", "KLMNO9012H"),
        ("BatteryHub India", "Mumbai", "Maharashtra", "400001", "Sneha Reddy", "sneha@batteryhub.in", "+91-9876543213", "23 Andheri West", "27PQRST3456I4W8", "PQRST3456I"),
        ("ChargePoint Network", "Delhi", "Delhi", "110001", "Vikram Singh", "vikram@chargepoint.in", "+91-9876543214", "56 Connaught Place", "07UVWXY7890J5V9", "UVWXY7890J"),
        ("PowerPack Dealers", "Pune", "Maharashtra", "411001", "Meera Joshi", "meera@powerpack.in", "+91-9876543215", "34 Koregaon Park", "27ZABCD1234K6U0", "ZABCD1234K"),
        ("ElectroDrive", "Kolkata", "West Bengal", "700001", "Sanjay Das", "sanjay@electro.in", "+91-9876543216", "91 Salt Lake", "19EFGHI5678L7T1", "EFGHI5678L"),
        ("SwiftCharge Pvt Ltd", "Ahmedabad", "Gujarat", "380001", "Neha Patel", "neha@swiftcharge.in", "+91-9876543217", "67 SG Highway", "24JKLMN9012M8S2", "JKLMN9012M"),
    ]

    # Get all user_ids and find ones that don't already have dealer profiles
    all_user_ids = [r[0] for r in conn.execute(text("SELECT id FROM users ORDER BY id")).fetchall()]
    used_user_ids = [r[0] for r in conn.execute(text("SELECT user_id FROM dealer_profiles")).fetchall()]
    available_ids = [uid for uid in all_user_ids if uid not in used_user_ids]
    
    # If not enough users, create placeholder user_ids by reusing first available
    if not available_ids:
        print("  ⚠ No available user_ids for dealers, skipping")
        return

    for i, (biz, city, state, pincode, contact, email, phone, addr, gst, pan) in enumerate(dealers):
        if i >= len(available_ids):
            break
        conn.execute(text("""
            INSERT INTO dealer_profiles (user_id, business_name, city, state, pincode, contact_person, contact_email, contact_phone, address_line1, gst_number, pan_number, is_active, created_at)
            VALUES (:uid, :biz, :city, :state, :pin, :contact, :email, :phone, :addr, :gst, :pan, true, :ts)
        """), {
            "uid": available_ids[i],
            "biz": biz, "city": city, "state": state, "pin": pincode,
            "contact": contact, "email": email, "phone": phone, "addr": addr,
            "gst": gst, "pan": pan,
            "ts": rand_date(180).isoformat(),
        })
    conn.commit()
    print(f"  ✓ Seeded {min(len(dealers), len(available_ids))} dealer_profiles")


def seed_dealer_applications(conn):
    if not ensure_table(conn, "dealer_applications"):
        print("⚠ dealer_applications table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM dealer_applications")).scalar()
    if existing > 3:
        print(f"  ✓ dealer_applications already has {existing} rows, skipping")
        return

    dealer_ids = [r[0] for r in conn.execute(text("SELECT id FROM dealer_profiles")).fetchall()]
    if not dealer_ids:
        print("  ⚠ No dealers to create applications for")
        return

    stages = ["SUBMITTED", "KYC_PENDING", "KYC_SUBMITTED", "REVIEW_PENDING", "FIELD_VISIT_SCHEDULED", "APPROVED"]
    for did in dealer_ids[:6]:
        stage = random.choice(stages)
        history = json.dumps([{"stage": stage, "timestamp": datetime.now(UTC).isoformat(), "notes": "Initial submission"}])
        conn.execute(text("""
            INSERT INTO dealer_applications (dealer_id, current_stage, risk_score, status_history, created_at, updated_at)
            VALUES (:did, :stage, :risk, CAST(:history AS jsonb), :ts, :ts)
        """), {
            "did": did, "stage": stage,
            "risk": round(random.uniform(0, 100), 1),
            "history": history,
            "ts": rand_date(60).isoformat(),
        })
    conn.commit()
    print(f"  ✓ Seeded {min(len(dealer_ids), 6)} dealer_applications")


def seed_dealer_documents(conn):
    if not ensure_table(conn, "dealer_documents"):
        print("⚠ dealer_documents table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM dealer_documents")).scalar()
    if existing > 3:
        print(f"  ✓ dealer_documents already has {existing} rows, skipping")
        return

    dealer_ids = [r[0] for r in conn.execute(text("SELECT id FROM dealer_profiles")).fetchall()]
    if not dealer_ids:
        return

    doc_types = ["gst_certificate", "pan_card", "business_license", "bank_statement", "address_proof", "partnership_agreement"]
    for did in dealer_ids:
        for dtype in random.sample(doc_types, min(3, len(doc_types))):
            conn.execute(text("""
                INSERT INTO dealer_documents (dealer_id, document_type, file_url, version, status, is_verified, uploaded_at)
                VALUES (:did, :dtype, :url, 1, :status, :verified, :ts)
            """), {
                "did": did, "dtype": dtype,
                "url": f"https://storage.wezu.com/docs/{did}/{dtype}.pdf",
                "status": random.choice(["pending", "approved", "pending"]),
                "verified": random.choice([True, False, False]),
                "ts": rand_date(30).isoformat(),
            })
    conn.commit()
    print("  ✓ Seeded dealer_documents")


def seed_commission_configs(conn):
    if not ensure_table(conn, "commission_configs"):
        print("⚠ commission_configs table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM commission_configs")).scalar()
    if existing > 3:
        print(f"  ✓ commission_configs already has {existing} rows, skipping")
        return

    dealer_ids = [r[0] for r in conn.execute(text("SELECT id FROM dealer_profiles")).fetchall()]
    tx_types = ["rental", "swap", "purchase"]
    for did in dealer_ids[:5]:
        for tx in tx_types:
            conn.execute(text("""
                INSERT INTO commission_configs (dealer_id, transaction_type, percentage, flat_fee, is_active, effective_from, created_at)
                VALUES (:did, :tx, :pct, :fee, true, :ts, :ts)
            """), {
                "did": did, "tx": tx,
                "pct": round(random.uniform(3, 12), 2),
                "fee": round(random.uniform(10, 100), 2),
                "ts": rand_date(120).isoformat(),
            })
    conn.commit()
    print("  ✓ Seeded commission_configs")


def seed_rentals(conn):
    if not ensure_table(conn, "rentals"):
        print("⚠ rentals table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM rentals")).scalar()
    if existing > 5:
        print(f"  ✓ rentals already has {existing} rows, skipping")
        return

    user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar() or 1
    station_ids = [r[0] for r in conn.execute(text("SELECT id FROM stations LIMIT 5")).fetchall()] or [1]
    battery_ids = [r[0] for r in conn.execute(text("SELECT id FROM batteries LIMIT 10")).fetchall()] or [1]

    statuses = ["ACTIVE", "ACTIVE", "ACTIVE", "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "OVERDUE", "CANCELLED"]
    for i in range(20):
        status = random.choice(statuses)
        start = rand_date(60)
        expected_end = start + timedelta(hours=random.randint(4, 72))
        end = expected_end + timedelta(hours=random.randint(-2, 24)) if status in ("COMPLETED", "CANCELLED") else None

        conn.execute(text("""
            INSERT INTO rentals (user_id, battery_id, start_station_id, start_time, expected_end_time, end_time,
                total_amount, security_deposit, late_fee, currency, is_deposit_refunded,
                status, start_battery_level, end_battery_level, distance_traveled_km, created_at, updated_at)
            VALUES (:uid, :bid, :sid, :start, :expected, :end,
                :amount, :deposit, :late_fee, 'INR', :refunded,
                CAST(:status AS rentalstatus), :level, :end_level, :dist, :start, :start)
        """), {
            "uid": user_id,
            "bid": random.choice(battery_ids),
            "sid": random.choice(station_ids),
            "start": start.isoformat(),
            "expected": expected_end.isoformat(),
            "end": end.isoformat() if end else None,
            "amount": round(random.uniform(50, 500), 2),
            "deposit": round(random.uniform(100, 300), 2),
            "late_fee": round(random.uniform(0, 50), 2) if status == "OVERDUE" else 0.0,
            "refunded": status == "COMPLETED",
            "status": status,
            "level": round(random.uniform(60, 100), 1),
            "end_level": round(random.uniform(10, 50), 1) if status in ("COMPLETED", "CANCELLED") else 0.0,
            "dist": round(random.uniform(5, 80), 1) if status in ("COMPLETED", "CANCELLED") else 0.0,
        })
    conn.commit()
    print("  ✓ Seeded 20 rentals")


def seed_swaps(conn):
    if not ensure_table(conn, "swap_sessions"):
        print("⚠ swap_sessions table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM swap_sessions")).scalar()
    if existing > 5:
        print(f"  ✓ swap_sessions already has {existing} rows, skipping")
        return

    user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar() or 1
    station_ids = [r[0] for r in conn.execute(text("SELECT id FROM stations LIMIT 5")).fetchall()] or [1]
    rental_ids = [r[0] for r in conn.execute(text("SELECT id FROM rentals LIMIT 10")).fetchall()] or [1]
    battery_ids = [r[0] for r in conn.execute(text("SELECT id FROM batteries LIMIT 10")).fetchall()] or [1]

    for i in range(15):
        old_soc = round(random.uniform(5, 30), 1)
        new_soc = round(random.uniform(70, 100), 1)
        conn.execute(text("""
            INSERT INTO swap_sessions (user_id, station_id, rental_id, old_battery_id, new_battery_id, old_battery_soc, new_battery_soc, status, created_at)
            VALUES (:uid, :sid, :rid, :ob, :nb, :osoc, :nsoc, :status, :ts)
        """), {
            "uid": user_id,
            "sid": random.choice(station_ids),
            "rid": random.choice(rental_ids),
            "ob": random.choice(battery_ids),
            "nb": random.choice(battery_ids),
            "osoc": old_soc, "nsoc": new_soc,
            "status": random.choice(["completed", "completed", "completed", "pending"]),
            "ts": rand_date(30).isoformat(),
        })
    conn.commit()
    print("  ✓ Seeded 15 swap_sessions")


def seed_purchases(conn):
    if not ensure_table(conn, "purchases"):
        print("⚠ purchases table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM purchases")).scalar()
    if existing > 3:
        print(f"  ✓ purchases already has {existing} rows, skipping")
        return

    user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar() or 1
    battery_ids = [r[0] for r in conn.execute(text("SELECT id FROM batteries LIMIT 10")).fetchall()] or [1]

    for i in range(12):
        conn.execute(text("""
            INSERT INTO purchases (user_id, battery_id, amount, timestamp)
            VALUES (:uid, :bid, :amount, :ts)
        """), {
            "uid": user_id,
            "bid": random.choice(battery_ids),
            "amount": round(random.uniform(5000, 25000), 2),
            "ts": rand_date(90).isoformat(),
        })
    conn.commit()
    print("  ✓ Seeded 12 purchases")


def seed_late_fees(conn):
    if not ensure_table(conn, "late_fees"):
        print("⚠ late_fees table missing, skipping")
        return

    existing = conn.execute(text("SELECT COUNT(*) FROM late_fees")).scalar()
    if existing > 3:
        print(f"  ✓ late_fees already has {existing} rows, skipping")
        return

    user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar() or 1
    # Get rental_ids that don't already have late fees (unique constraint on rental_id)
    rental_ids = [r[0] for r in conn.execute(text(
        "SELECT r.id FROM rentals r LEFT JOIN late_fees lf ON r.id = lf.rental_id WHERE lf.id IS NULL LIMIT 10"
    )).fetchall()]
    if not rental_ids:
        print("  ⚠ No available rental_ids for late fees, skipping")
        return

    now = datetime.now(UTC)
    for i, rid in enumerate(rental_ids[:10]):
        days = random.randint(1, 14)
        daily_rate = round(random.uniform(20, 100), 2)
        base_fee = round(days * daily_rate, 2)
        penalty = round(base_fee * random.uniform(0, 0.3), 2)
        total = round(base_fee + penalty, 2)
        paid = round(random.uniform(0, total), 2) if random.random() > 0.4 else 0
        orig_end = now - timedelta(days=days + random.randint(1, 10))
        ts = rand_date(45)
        conn.execute(text("""
            INSERT INTO late_fees (rental_id, user_id, original_end_date, days_overdue, daily_late_fee_rate, base_late_fee, progressive_penalty, total_late_fee, amount_paid, amount_waived, amount_outstanding, payment_status, created_at, updated_at)
            VALUES (:rid, :uid, :orig_end, :days, :rate, :base, :penalty, :total, :paid, 0, :outstanding, :status, :ts, :ts)
        """), {
            "rid": rid,
            "uid": user_id,
            "orig_end": orig_end.isoformat(),
            "days": days,
            "rate": daily_rate,
            "base": base_fee,
            "penalty": penalty,
            "total": total,
            "paid": paid,
            "outstanding": round(total - paid, 2),
            "status": "PAID" if paid >= total else ("PARTIAL" if paid > 0 else "PENDING"),
            "ts": ts.isoformat(),
        })
    conn.commit()
    print("  ✓ Seeded 10 late_fees")


def run_seed(label, seed_fn):
    """Run a seed function with its own connection to isolate transaction failures."""
    print(f"\n{label}")
    try:
        with engine.connect() as conn:
            seed_fn(conn)
    except Exception as e:
        print(f"  ✗ Error: {e}")


def main():
    print("=" * 50)
    print("🚀 WEZU Admin Portal — Master Seed Script")
    print("=" * 50)

    run_seed("📦 Seeding inventory audit logs...", seed_audit_trails)
    run_seed("🔧 Seeding maintenance records...", seed_maintenance)
    run_seed("🤝 Seeding dealer profiles...", seed_dealers)
    run_seed("📝 Seeding dealer applications...", seed_dealer_applications)
    run_seed("📄 Seeding dealer documents...", seed_dealer_documents)
    run_seed("💰 Seeding commission configs...", seed_commission_configs)
    run_seed("🔋 Seeding rentals...", seed_rentals)
    run_seed("🔄 Seeding swap sessions...", seed_swaps)
    run_seed("🛒 Seeding purchases...", seed_purchases)
    run_seed("⏰ Seeding late fees...", seed_late_fees)

    print("\n" + "=" * 50)
    print("✅ Seeding complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
