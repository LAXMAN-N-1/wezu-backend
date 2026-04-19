from __future__ import annotations
"""
Comprehensive Dealer Portal Seed Script
Uses verified actual DB schema - columns, enums, NOT NULL constraints.
"""
import sys
import os
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from sqlalchemy import text
from sqlmodel import Session
from app.core.database import engine

UTC = timezone.utc
NOW = datetime.now(UTC)

DEALER_EMAIL = "dealer@wezu.com"
DEALER_PASSWORD_HASH = "$2b$12$LQv3c1yqBo9SkvXS7QTJPOsnGD3JlsXfZVh9t7j0k8Ym6Q1oLzI6a"


def seed():
    with Session(engine) as db:
        print("🚀 Starting comprehensive dealer portal seed...\n")

        # ═══════════════════════════════════
        # 1. DEALER USER (verified: user_type enum, status enum)
        # ═══════════════════════════════════
        existing_user = db.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": DEALER_EMAIL}
        ).first()

        if existing_user:
            dealer_user_id = existing_user[0]
            print(f"  ✓ Dealer user exists (id={dealer_user_id})")
        else:
            db.execute(text("""
                INSERT INTO users (email, hashed_password, full_name, phone_number,
                    user_type, status, is_superuser, failed_login_attempts,
                    kyc_status, two_factor_enabled, biometric_login_enabled,
                    force_password_change, is_deleted, created_at, updated_at)
                VALUES (:e, :p, 'Green Energy Corp', '+919876543210',
                    'DEALER', 'ACTIVE', false, 0,
                    'APPROVED', false, false,
                    false, false, :now, :now)
            """), {"e": DEALER_EMAIL, "p": DEALER_PASSWORD_HASH, "now": NOW})
            db.commit()
            dealer_user_id = db.execute(
                text("SELECT id FROM users WHERE email = :e"), {"e": DEALER_EMAIL}
            ).scalar()
            print(f"  ✓ Dealer user CREATED (id={dealer_user_id})")

        # ═══════════════════════════════════
        # 2. DEALER PROFILE
        # ═══════════════════════════════════
        existing_profile = db.execute(
            text("SELECT id FROM dealer_profiles WHERE user_id = :u"), {"u": dealer_user_id}
        ).first()

        if existing_profile:
            dealer_id = existing_profile[0]
            print(f"  ✓ Dealer profile exists (id={dealer_id})")
        else:
            db.execute(text("""
                INSERT INTO dealer_profiles (
                    user_id, business_name, contact_person, contact_email, contact_phone,
                    gst_number, pan_number, address_line1, city, state, pincode,
                    is_active, created_at, updated_at
                ) VALUES (
                    :u, 'Green Energy Corp', 'Rajesh Sharma', 'rajesh@greenenergy.com', '+919876543210',
                    '29AABCU9603R1ZM', 'AABCU9603R', '42, MG Road, Koramangala', 'Bangalore', 'Karnataka', '560034',
                    true, :now, :now
                )
            """), {"u": dealer_user_id, "now": NOW})
            db.commit()
            dealer_id = db.execute(
                text("SELECT id FROM dealer_profiles WHERE user_id = :u"), {"u": dealer_user_id}
            ).scalar()
            print(f"  ✓ Dealer profile CREATED (id={dealer_id})")

        # ═══════════════════════════════════
        # 3. STATIONS (all NOT NULL columns included)
        # ═══════════════════════════════════
        station_count = db.execute(
            text("SELECT count(*) FROM stations WHERE dealer_id = :d"), {"d": dealer_id}
        ).scalar()

        station_ids = []
        if station_count >= 4:
            rows = db.execute(
                text("SELECT id FROM stations WHERE dealer_id = :d ORDER BY id"), {"d": dealer_id}
            ).all()
            station_ids = [r[0] for r in rows]
            print(f"  ✓ {len(station_ids)} stations exist")
        else:
            stations_data = [
                ("WEZU Hub Koramangala", "42 MG Road, Koramangala", "Bangalore", 12.9352, 77.6245, 12, "OPERATIONAL", 4.5, True, 8, 4),
                ("WEZU Station Indiranagar", "100 Feet Road, Indiranagar", "Bangalore", 12.9784, 77.6408, 8, "OPERATIONAL", 4.2, True, 5, 3),
                ("WEZU Point Whitefield", "ITPL Road, Whitefield", "Bangalore", 12.9698, 77.7500, 10, "OPERATIONAL", 4.7, False, 7, 3),
                ("WEZU Express HSR Layout", "27th Main, HSR Layout", "Bangalore", 12.9116, 77.6474, 6, "MAINTENANCE", 3.8, True, 3, 3),
            ]
            for name, addr, city, lat, lon, slots, status, rating, is247, avail_batt, avail_slots in stations_data:
                db.execute(text("""
                    INSERT INTO stations (
                        name, address, city, latitude, longitude, total_slots, status,
                        rating, is_24x7, dealer_id, station_type,
                        available_batteries, available_slots,
                        temperature_control, approval_status, total_reviews, low_stock_threshold_pct,
                        contact_phone, operating_hours,
                        last_maintenance_date, last_heartbeat, created_at, updated_at
                    ) VALUES (
                        :n, :a, :c, :lat, :lon, :slots, :st, :r, :is247, :d, 'automated',
                        :ab, :asl,
                        true, 'approved', :reviews, 20.0,
                        :phone, :oh, :lm, :lh, :now, :now
                    )
                """), {
                    "n": name, "a": addr, "c": city, "lat": lat, "lon": lon,
                    "slots": slots, "st": status, "r": rating, "is247": is247, "d": dealer_id,
                    "ab": avail_batt, "asl": avail_slots,
                    "reviews": random.randint(15, 120),
                    "phone": f"+91-80-4567-{random.randint(1000,9999)}",
                    "oh": "24/7" if is247 else "06:00 - 22:00",
                    "lm": NOW - timedelta(days=random.randint(5, 20)),
                    "lh": NOW - timedelta(minutes=random.randint(1, 30)),
                    "now": NOW,
                })
            db.commit()
            rows = db.execute(
                text("SELECT id FROM stations WHERE dealer_id = :d ORDER BY id"), {"d": dealer_id}
            ).all()
            station_ids = [r[0] for r in rows]
            print(f"  ✓ {len(station_ids)} stations CREATED")

        # ═══════════════════════════════════
        # 4. INVENTORY
        # ═══════════════════════════════════
        inv_count = db.execute(
            text("SELECT count(*) FROM dealer_inventories WHERE dealer_id = :d"), {"d": dealer_id}
        ).scalar()

        if inv_count >= 3:
            print(f"  ✓ Inventory exists ({inv_count} items)")
        else:
            models = [
                ("WZ-LFP-48V", 32, 5, 2, 8, 50),
                ("WZ-LFP-60V", 18, 3, 1, 5, 30),
                ("WZ-NMC-72V", 12, 2, 0, 4, 20),
                ("WZ-LFP-48V-PRO", 8, 1, 0, 3, 15),
            ]
            for model, qty, res, dmg, reorder, cap in models:
                db.execute(text("""
                    INSERT INTO dealer_inventories (
                        dealer_id, battery_model, quantity_available, quantity_reserved,
                        quantity_damaged, reorder_level, max_capacity, created_at, updated_at
                    ) VALUES (:d, :m, :q, :r, :dm, :rl, :c, :now, :now)
                """), {
                    "d": dealer_id, "m": model, "q": qty, "r": res,
                    "dm": dmg, "rl": reorder, "c": cap, "now": NOW,
                })
            db.commit()
            print("  ✓ Inventory CREATED (4 battery models)")

        # ═══════════════════════════════════
        # 5. CUSTOMER USERS + RENTALS
        #    users: user_type='CUSTOMER', status='ACTIVE' (enums)
        #    rentals: battery_id, start_time, expected_end_time, total_amount,
        #             security_deposit, late_fee, currency, is_deposit_refunded,
        #             start_battery_level, end_battery_level, distance_traveled_km
        # ═══════════════════════════════════
        customer_names = [
            ("Priya Patel", "priya.patel@demo.com", "+919001000001"),
            ("Amit Kumar", "amit.kumar@demo.com", "+919001000002"),
            ("Sneha Reddy", "sneha.reddy@demo.com", "+919001000003"),
            ("Vikram Singh", "vikram.singh@demo.com", "+919001000004"),
            ("Ananya Gupta", "ananya.gupta@demo.com", "+919001000005"),
            ("Rahul Verma", "rahul.verma@demo.com", "+919001000006"),
            ("Deepika Nair", "deepika.nair@demo.com", "+919001000007"),
            ("Karthik Iyer", "karthik.iyer@demo.com", "+919001000008"),
        ]
        customer_ids = []
        for name, email, phone in customer_names:
            existing = db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email}).first()
            if existing:
                customer_ids.append(existing[0])
            else:
                db.execute(text("""
                    INSERT INTO users (email, hashed_password, full_name, phone_number,
                        user_type, status, is_superuser, failed_login_attempts,
                        kyc_status, two_factor_enabled, biometric_login_enabled,
                        force_password_change, is_deleted, created_at, updated_at)
                    VALUES (:e, :p, :n, :ph,
                        'CUSTOMER', 'ACTIVE', false, 0,
                        'APPROVED', false, false,
                        false, false, :ca, :ca)
                """), {"e": email, "p": DEALER_PASSWORD_HASH, "n": name, "ph": phone,
                       "ca": NOW - timedelta(days=random.randint(30, 180))})
                db.commit()
                cid = db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email}).scalar()
                customer_ids.append(cid)
        print(f"  ✓ {len(customer_ids)} customer users ready")

        # Get battery IDs from the batteries table
        battery_ids = [r[0] for r in db.execute(text("SELECT id FROM batteries LIMIT 10")).all()]
        if not battery_ids:
            battery_ids = [1]  # fallback
            print("  ⚠ No batteries found, using fallback id=1")

        # Rentals (all NOT NULL columns filled)
        rental_count = 0
        for sid in station_ids:
            c = db.execute(text("SELECT count(*) FROM rentals WHERE start_station_id = :s"), {"s": sid}).scalar()
            rental_count += c

        if rental_count >= 20:
            print(f"  ✓ Rentals exist ({rental_count})")
        else:
            created_count = 0
            for i in range(30):
                cust_id = random.choice(customer_ids)
                start_sid = random.choice(station_ids)
                end_sid = random.choice(station_ids)
                batt_id = random.choice(battery_ids)
                created = NOW - timedelta(days=random.randint(1, 60), hours=random.randint(0, 23))
                amount = round(random.uniform(25, 150), 2)
                status = random.choice(["COMPLETED", "COMPLETED", "COMPLETED", "ACTIVE", "COMPLETED"])
                duration_hrs = random.randint(1, 48)
                try:
                    db.execute(text("""
                        INSERT INTO rentals (
                            user_id, battery_id, start_station_id, end_station_id, status,
                            total_amount, security_deposit, late_fee, currency, is_deposit_refunded,
                            start_time, expected_end_time, end_time,
                            start_battery_level, end_battery_level, distance_traveled_km,
                            created_at, updated_at
                        ) VALUES (
                            :u, :bid, :ss, :es, :st,
                            :amt, :dep, :lf, 'INR', :refunded,
                            :start, :expected, :endtime,
                            :sbl, :ebl, :dist,
                            :ca, :ca
                        )
                    """), {
                        "u": cust_id, "bid": batt_id, "ss": start_sid, "es": end_sid,
                        "st": status, "amt": amount,
                        "dep": round(random.uniform(100, 500), 2),
                        "lf": 0.0 if status == "COMPLETED" else round(random.uniform(10, 50), 2),
                        "refunded": status == "COMPLETED",
                        "start": created,
                        "expected": created + timedelta(hours=duration_hrs),
                        "endtime": created + timedelta(hours=duration_hrs + random.randint(-1, 3)) if status == "COMPLETED" else None,
                        "sbl": random.randint(80, 100),
                        "ebl": random.randint(10, 60),
                        "dist": round(random.uniform(5, 80), 1),
                        "ca": created,
                    })
                    created_count += 1
                except Exception as e:
                    db.rollback()
                    # Skip duplicate / FK violations silently
                    continue
            db.commit()
            print(f"  ✓ {created_count} Rentals CREATED")

        # ═══════════════════════════════════
        # 6. SUPPORT TICKETS
        # ═══════════════════════════════════
        ticket_count = db.execute(
            text("SELECT count(*) FROM support_tickets WHERE user_id = :u"), {"u": dealer_user_id}
        ).scalar()

        if ticket_count >= 5:
            print(f"  ✓ Tickets exist ({ticket_count})")
        else:
            tickets = [
                ("Battery not charging at slot 3", "Station Koramangala slot 3 has a faulty connector", "Hardware", "HIGH", "OPEN"),
                ("Refund request - failed swap", "Customer paid but swap didn't complete", "Billing", "MEDIUM", "OPEN"),
                ("Station offline for 2 hours", "Whitefield station went offline suddenly", "Technical", "CRITICAL", "IN_PROGRESS"),
                ("App sync error after swap", "Battery status not updating on customer app", "Software", "LOW", "OPEN"),
                ("Request for additional slots", "Need 4 more battery slots at Indiranagar", "General", "LOW", "RESOLVED"),
                ("Monthly maintenance scheduled", "HSR station needs preventive maintenance", "Maintenance", "MEDIUM", "OPEN"),
                ("Customer complaint - wrong charge", "Customer charged twice for single swap", "Billing", "HIGH", "IN_PROGRESS"),
            ]
            for subj, desc, cat, pri, st in tickets:
                db.execute(text("""
                    INSERT INTO support_tickets (user_id, subject, description, category, priority, status, created_at, updated_at)
                    VALUES (:u, :s, :desc, :cat, :p, :st, :ca, :ca)
                """), {
                    "u": dealer_user_id, "s": subj, "desc": desc, "cat": cat, "p": pri, "st": st,
                    "ca": NOW - timedelta(days=random.randint(0, 15), hours=random.randint(0, 23)),
                })
            db.commit()
            print("  ✓ 7 Support tickets CREATED")

        # ═══════════════════════════════════
        # 7. DOCUMENTS
        # ═══════════════════════════════════
        doc_count = db.execute(
            text("SELECT count(*) FROM dealer_documents WHERE dealer_id = :d"), {"d": dealer_id}
        ).scalar()

        if doc_count >= 4:
            print(f"  ✓ Documents exist ({doc_count})")
        else:
            docs = [
                ("GST_CERTIFICATE", "verification", "VERIFIED", "https://storage.wezu.com/docs/gst_cert.pdf"),
                ("PAN_CARD", "verification", "VERIFIED", "https://storage.wezu.com/docs/pan_card.pdf"),
                ("BUSINESS_LICENSE", "compliance", "PENDING", "https://storage.wezu.com/docs/biz_license.pdf"),
                ("INSURANCE_POLICY", "compliance", "VERIFIED", "https://storage.wezu.com/docs/insurance.pdf"),
                ("CANCELLED_CHEQUE", "financial", "VERIFIED", "https://storage.wezu.com/docs/cheque.pdf"),
                ("SAFETY_CERTIFICATE", "operational", "PENDING", "https://storage.wezu.com/docs/safety_cert.pdf"),
                ("ELECTRICAL_COMPLIANCE", "operational", "VERIFIED", "https://storage.wezu.com/docs/electrical.pdf"),
            ]
            for doc_type, category, status, url in docs:
                valid = NOW + timedelta(days=random.randint(90, 365)) if status == "VERIFIED" else None
                db.execute(text("""
                    INSERT INTO dealer_documents (
                        dealer_id, document_type, category, file_url, status,
                        version, valid_until, uploaded_at, is_verified
                    ) VALUES (:d, :dt, :cat, :url, :st, 1, :vu, :now, :iv)
                """), {
                    "d": dealer_id, "dt": doc_type, "cat": category, "url": url,
                    "st": status, "vu": valid, "now": NOW - timedelta(days=random.randint(5, 60)),
                    "iv": status == "VERIFIED",
                })
            db.commit()
            print("  ✓ 7 Documents CREATED")

        # ═══════════════════════════════════
        # 8. NOTIFICATIONS
        # ═══════════════════════════════════
        notif_count = db.execute(
            text("SELECT count(*) FROM notifications WHERE user_id = :u"), {"u": dealer_user_id}
        ).scalar()

        if notif_count >= 5:
            print(f"  ✓ Notifications exist ({notif_count})")
        else:
            notifs = [
                ("low_stock", "Low Stock Alert", "WZ-LFP-48V inventory is below reorder level at Koramangala station", False),
                ("revenue", "Revenue Milestone", "Congratulations! You crossed ₹1,00,000 revenue this month", True),
                ("ticket", "Ticket Update", "Ticket #3 (Station offline) has been assigned to a technician", False),
                ("maintenance", "Maintenance Due", "HSR Layout station maintenance is overdue by 5 days", False),
                ("system", "System Update", "New portal features released: Analytics dashboard and Campaign manager", True),
                ("onboarding", "Welcome to WEZU", "Your dealer profile has been verified. Start managing your stations!", True),
                ("payment", "Commission Credited", "₹12,450 commission has been credited to your bank account", True),
                ("alert", "High Utilization", "Whitefield station utilization hit 92% — consider adding more slots", False),
            ]
            for ntype, title, msg, is_read in notifs:
                db.execute(text("""
                    INSERT INTO notifications (user_id, type, title, message, channel, status, is_read, created_at)
                    VALUES (:u, :t, :title, :msg, 'push', 'sent', :ir, :ca)
                """), {
                    "u": dealer_user_id, "t": ntype, "title": title, "msg": msg,
                    "ir": is_read, "ca": NOW - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23)),
                })
            db.commit()
            print("  ✓ 8 Notifications CREATED")

        # ═══════════════════════════════════
        # 9. ONBOARDING APPLICATION
        # ═══════════════════════════════════
        app_exists = db.execute(
            text("SELECT id FROM dealer_applications WHERE dealer_id = :d"), {"d": dealer_id}
        ).first()

        if app_exists:
            print("  ✓ Onboarding application exists")
        else:
            db.execute(text("""
                INSERT INTO dealer_applications (
                    dealer_id, current_stage, risk_score, status_history, created_at, updated_at
                ) VALUES (
                    :d, 'APPROVED', 15.0,
                    '[{"stage":"SUBMITTED","timestamp":"2026-03-01T10:00:00"},{"stage":"APPROVED","timestamp":"2026-03-07T12:00:00"}]'::jsonb,
                    :now, :now
                )
            """), {"d": dealer_id, "now": NOW - timedelta(days=24)})
            db.commit()
            print("  ✓ Onboarding application CREATED (APPROVED)")

        # ═══════════════════════════════════
        # 10. PROMOTIONS (dealer campaigns)
        # ═══════════════════════════════════
        promo_count = db.execute(
            text("SELECT count(*) FROM dealer_promotions WHERE dealer_id = :d"), {"d": dealer_id}
        ).scalar()

        if promo_count >= 2:
            print(f"  ✓ Promotions exist ({promo_count})")
        else:
            promos = [
                ("Summer Swap Fest", "SUMMER25", "PERCENTAGE", 25.0, True),
                ("New User Welcome", "NEWUSER10", "PERCENTAGE", 10.0, True),
                ("Monsoon Charge", "MONSOON15", "FLAT", 15.0, False),
            ]
            for name, code, dtype, val, active in promos:
                try:
                    db.execute(text("""
                        INSERT INTO dealer_promotions (
                            dealer_id, name, promo_code, discount_type, discount_value,
                            start_date, end_date, is_active, created_at,
                            requires_approval, usage_limit_per_user, usage_count, applicable_to
                        ) VALUES (
                            :d, :n, :c, :dt, :dv,
                            :sd, :ed, :ia, :now,
                            true, 5, :uc, 'ALL'
                        )
                    """), {
                        "d": dealer_id, "n": name, "c": code, "dt": dtype, "dv": val,
                        "sd": NOW - timedelta(days=random.randint(5, 30)),
                        "ed": NOW + timedelta(days=random.randint(15, 60)),
                        "ia": active, "now": NOW,
                        "uc": random.randint(10, 200),
                    })
                except Exception:
                    db.rollback()
                    continue
            db.commit()
            print("  ✓ 3 Promotions/Campaigns CREATED")

        # ═══════════════════════════════════
        # 11. NOTIFICATION PREFERENCES
        # ═══════════════════════════════════
        try:
            prefs_exist = db.execute(
                text("SELECT id FROM notification_preferences WHERE user_id = :u"), {"u": dealer_user_id}
            ).first()
            if not prefs_exist:
                db.execute(text("""
                    INSERT INTO notification_preferences (
                        user_id, notifications_enabled, email_enabled, sms_enabled, push_enabled,
                        battery_alerts_push, battery_alerts_email, maintenance_push, maintenance_email,
                        created_at, updated_at
                    ) VALUES (:u, true, true, false, true, true, true, true, true, :now, :now)
                """), {"u": dealer_user_id, "now": NOW})
                db.commit()
                print("  ✓ Notification preferences CREATED")
            else:
                print("  ✓ Notification preferences exist")
        except Exception as e:
            db.rollback()
            print(f"  ⚠ Notification prefs skipped: {e}")

        # ═══════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════
        print("\n" + "=" * 50)
        print("✅ DEALER PORTAL SEED COMPLETE!")
        print("=" * 50)
        print(f"\n  📧 Login: {DEALER_EMAIL}")
        print(f"  🔑 Password: dealer123")
        print(f"  🏢 Business: Green Energy Corp")
        print(f"  🏪 Stations: {len(station_ids)}")
        print(f"  📦 Inventory: 4 battery models")
        print(f"  👥 Customers: {len(customer_ids)}")
        print(f"  📄 Documents: 7")
        print(f"  🎫 Tickets: 7")
        print(f"  🔔 Notifications: 8")
        print(f"  📢 Campaigns: 3")
        print()


if __name__ == "__main__":
    seed()
