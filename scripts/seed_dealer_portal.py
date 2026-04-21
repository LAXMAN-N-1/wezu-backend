"""
Comprehensive Dealer Portal Data Seeder
Seeds all data required for the 11 dealer portal screens.
Run: cd backend && python scripts/seed_dealer_portal.py
"""
import os, sys, random, uuid
from datetime import datetime, UTC, timedelta

_SEED_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select, func
from app.db.session import engine
import app.models.all  # Fix mapper init issues in standalone scripts
import app.models.all
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile, DealerDocument
from app.models.station import Station, StationStatus, StationSlot
from app.models.battery import Battery, BatteryStatus, BatteryHealth, LocationType
from app.models.dealer_inventory import DealerInventory, InventoryTransaction
from app.models.rental import Rental, RentalStatus
from app.models.support import SupportTicket, TicketStatus, TicketPriority, TicketMessage
from app.models.notification import Notification
from app.models.financial import Transaction, TransactionStatus, Wallet
from app.models.commission import CommissionLog
from app.models.dealer_promotion import DealerPromotion
from app.models.maintenance import MaintenanceRecord
from app.core.security import get_password_hash

NOW = datetime.now(UTC)


def _safe_commit(session):
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"  ⚠ Commit failed: {e}")


def seed_all():
    with Session(engine) as db:
        print("=" * 60)
        print("WEZU Dealer Portal — Full Data Seeder")
        print("=" * 60)

        # ── 1. Ensure dealer user + profile ──────────────────────
        print("\n[1/10] Checking dealer user...")
        dealer_user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if not dealer_user:
            dealer_user = User(
                email="dealer@wezu.com",
                phone_number="8888888888",
                full_name="Laxman Kumar",
                hashed_password=get_password_hash("laxman123"),
                user_type=UserType.DEALER,
                status=UserStatus.ACTIVE,
            )
            db.add(dealer_user)
            db.commit()
            db.refresh(dealer_user)
            print(f"  ✓ Created dealer user id={dealer_user.id}")
        else:
            dealer_user.hashed_password = get_password_hash("laxman123")
            db.add(dealer_user)
            db.commit()
            print(f"  ✓ Updated dealer user password id={dealer_user.id}")

        dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == dealer_user.id)).first()
        if not dealer:
            dealer = DealerProfile(
                user_id=dealer_user.id,
                business_name="GreenCharge Hyderabad",
                contact_person="Laxman Kumar",
                contact_email="dealer@wezu.com",
                contact_phone="8888888888",
                address_line1="Plot 42, Madhapur Tech Zone",
                city="Hyderabad",
                state="Telangana",
                pincode="500081",
                gst_number="36AABCU9603R1ZM",
                pan_number="AABCU9603R",
                is_active=True,
            )
            db.add(dealer)
            db.commit()
            db.refresh(dealer)
            print(f"  ✓ Created dealer profile id={dealer.id}")
        else:
            print(f"  ✓ Dealer profile exists id={dealer.id}")

        # ── 2. Seed customer users ────────────────────────────────
        print("\n[2/10] Seeding customers...")
        customers = []
        customer_names = [
            "Ravi Sharma", "Priya Singh", "Amit Patel", "Sneha Reddy",
            "Vikram Malhotra", "Kavita Nair", "Rajesh Kumar", "Anjali Gupta",
            "Mohammed Ali", "Deepa Krishnan"
        ]
        for i, name in enumerate(customer_names):
            email = f"customer_{i}@wezutest.com"
            user = db.exec(select(User).where(User.email == email)).first()
            if not user:
                user = User(
                    email=email,
                    phone_number=f"900000{i:04d}",
                    full_name=name,
                    hashed_password=get_password_hash(_SEED_PASSWORD),
                    user_type=UserType.CUSTOMER,
                    status=UserStatus.ACTIVE,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                # Wallet
                w = db.exec(select(Wallet).where(Wallet.user_id == user.id)).first()
                if not w:
                    db.add(Wallet(user_id=user.id, balance=random.uniform(200, 3000)))
                    db.commit()
            customers.append(user)
        print(f"  ✓ {len(customers)} customers ready")

        # ── 3. Seed stations ──────────────────────────────────────
        print("\n[3/10] Seeding stations...")
        station_configs = [
            ("Madhapur SwapHub", "Plot 42, Madhapur IT Park", "Hyderabad", 17.4484, 78.3908, "active", 12, True, 4.7),
            ("Gachibowli EnergyPoint", "DLF Cyber City, Gachibowli", "Hyderabad", 17.4401, 78.3489, "active", 15, True, 4.5),
            ("Banjara Hills Station", "Road No. 12, Banjara Hills", "Hyderabad", 17.4156, 78.4347, "active", 10, False, 4.3),
            ("Hitech City Hub", "Hitech City Metro, Cyber Towers", "Hyderabad", 17.4474, 78.3762, "maintenance", 8, True, 4.1),
            ("Kukatpally Power Center", "KPHB Colony Main Road", "Hyderabad", 17.4947, 78.3996, "active", 20, True, 4.8),
        ]
        stations = []
        for name, addr, city, lat, lng, status, slots, is_24, rating in station_configs:
            st = db.exec(select(Station).where(Station.name == name, Station.dealer_id == dealer.id)).first()
            if not st:
                last_maint = NOW - timedelta(days=random.randint(5, 45))
                st = Station(
                    name=name, address=addr, city=city,
                    latitude=lat, longitude=lng,
                    station_type="automated",
                    total_slots=slots,
                    status=status,
                    is_24x7=is_24,
                    rating=rating,
                    dealer_id=dealer.id,
                    available_batteries=random.randint(3, slots),
                    available_slots=random.randint(2, slots),
                    last_maintenance_date=last_maint,
                    contact_phone="040-12345678",
                    operating_hours='{"mon-sat": "06:00-22:00", "sun": "08:00-20:00"}',
                    last_heartbeat=NOW - timedelta(minutes=random.randint(1, 30)),
                )
                db.add(st)
                db.commit()
                db.refresh(st)

                # Create slots
                for slot_i in range(st.total_slots):
                    slot_status = random.choice(["empty", "charging", "ready", "ready", "empty"])
                    db.add(StationSlot(
                        station_id=st.id,
                        slot_number=slot_i + 1,
                        status=slot_status,
                        is_locked=slot_status == "empty",
                        current_power_w=random.uniform(0, 500) if slot_status == "charging" else 0,
                    ))
                db.commit()
            stations.append(st)
        print(f"  ✓ {len(stations)} stations ready")

        # ── 4. Seed dealer inventory ──────────────────────────────
        print("\n[4/10] Seeding inventory...")
        battery_models = [
            ("WZU-48V/30Ah", 45, 12, 3, 10, 100),
            ("WZU-60V/24Ah", 30, 8, 2, 8, 80),
            ("WZU-72V/20Ah", 20, 5, 1, 5, 50),
            ("WZU-48V/40Ah Pro", 15, 3, 0, 5, 40),
            ("WZU-60V/30Ah Max", 25, 6, 2, 8, 60),
        ]
        for model, avail, reserved, damaged, reorder, cap in battery_models:
            inv = db.exec(select(DealerInventory).where(
                DealerInventory.dealer_id == dealer.id,
                DealerInventory.battery_model == model
            )).first()
            if not inv:
                inv = DealerInventory(
                    dealer_id=dealer.id,
                    battery_model=model,
                    quantity_available=avail,
                    quantity_reserved=reserved,
                    quantity_damaged=damaged,
                    reorder_level=reorder,
                    max_capacity=cap,
                    last_restocked_at=NOW - timedelta(days=random.randint(3, 20)),
                )
                db.add(inv)
                db.commit()
                db.refresh(inv)

                # Seed inventory transactions (movements)
                for j in range(random.randint(3, 8)):
                    tx_type = random.choice(["RECEIVED", "SOLD", "RETURNED", "DAMAGED", "ADJUSTED"])
                    db.add(InventoryTransaction(
                        inventory_id=inv.id,
                        transaction_type=tx_type,
                        quantity=random.randint(1, 10),
                        reference_type=random.choice(["ORDER", "RENTAL", "MANUAL"]),
                        notes=f"Auto-seeded {tx_type.lower()} movement",
                        performed_by=dealer_user.id,
                        created_at=NOW - timedelta(days=random.randint(0, 30)),
                    ))
                db.commit()
        print(f"  ✓ {len(battery_models)} inventory models seeded")

        # ── 5. Seed rentals (from dealer stations) ────────────────
        print("\n[5/10] Seeding rentals...")
        station_ids = [s.id for s in stations]
        all_batteries = db.exec(select(Battery)).all()
        if not all_batteries:
            print("  ⚠ No batteries found — skipping rentals")
        rental_count = 0
        for i in range(35):
            if not all_batteries:
                break
            user = random.choice(customers)
            start_st = random.choice(stations)
            is_active = random.random() < 0.3
            start_time = NOW - timedelta(days=random.randint(0, 30), hours=random.randint(0, 12))

            r = Rental(
                user_id=user.id,
                battery_id=random.choice(all_batteries).id,
                start_station_id=start_st.id,
                start_time=start_time,
                expected_end_time=start_time + timedelta(hours=24),
                status=RentalStatus.ACTIVE if is_active else RentalStatus.COMPLETED,
                total_amount=random.uniform(80, 500),
            )
            if not is_active:
                r.end_time = r.start_time + timedelta(hours=random.randint(2, 48))
                r.end_station_id = random.choice(stations).id
                r.distance_traveled_km = random.uniform(5, 80)
            db.add(r)
            rental_count += 1
        _safe_commit(db)
        print(f"  ✓ {rental_count} rentals seeded")

        # ── 5.5. Seed swap sessions ──────────────────────────────
        print("\n[5.5/10] Seeding swap sessions...")
        from app.models.swap import SwapSession
        swap_count = 0
        for i in range(150):
            if not all_batteries:
                break
            user = random.choice(customers)
            st = random.choice(stations)
            created = NOW - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            
            swap = SwapSession(
                user_id=user.id,
                station_id=st.id,
                old_battery_id=random.choice(all_batteries).id,
                new_battery_id=random.choice(all_batteries).id,
                old_battery_soc=random.uniform(5.0, 30.0),
                new_battery_soc=random.uniform(90.0, 100.0),
                swap_amount=random.uniform(20.0, 150.0),
                currency="INR",
                status="completed",
                payment_status="paid",
                created_at=created,
                completed_at=created + timedelta(minutes=random.randint(1, 5)),
            )
            db.add(swap)
            swap_count += 1
        _safe_commit(db)
        print(f"  ✓ {swap_count} swap sessions seeded")

        # ── 6. Seed commission logs (revenue data) ────────────────
        print("\n[6/10] Seeding commission logs...")
        # Create transactions first for FK references
        txns = db.exec(select(Transaction).limit(5)).all()
        txn_id = txns[0].id if txns else None

        if txn_id:
            for day in range(90):
                date = NOW - timedelta(days=day)
                num_commissions = random.randint(1, 5) if day < 30 else random.randint(0, 2)
                for _ in range(num_commissions):
                    existing = db.exec(select(func.count(CommissionLog.id)).where(
                        CommissionLog.dealer_id == dealer_user.id,
                    )).one()
                    if existing and existing > 500:
                        break
                    db.add(CommissionLog(
                        transaction_id=txn_id,
                        dealer_id=dealer_user.id,
                        amount=random.uniform(50, 800),
                        status=random.choice(["paid", "paid", "pending"]),
                        created_at=date,
                    ))
            _safe_commit(db)
            print(f"  ✓ Commission logs seeded")
        else:
            print("  ⚠ No transactions found — skipping commission logs")

        # ── 6.5. Seed settlements (platform fees, payouts) ──────────────
        print("\n[6.5/10] Seeding settlements...")
        from app.models.settlement import Settlement
        for m in range(3):
            s_date = (NOW - timedelta(days=30*m)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Find last day by adding 31 days and replacing day=1, then back 1 day
            next_m = s_date.month % 12 + 1
            next_y = s_date.year + (s_date.month // 12)
            temp = s_date.replace(year=next_y, month=next_m, day=1)
            e_date = (temp - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            
            existing = db.exec(select(Settlement).where(Settlement.dealer_id == dealer.id, Settlement.settlement_month == s_date.strftime("%Y-%m"))).first()
            if not existing:
                db.add(Settlement(
                    dealer_id=dealer.id,
                    settlement_month=s_date.strftime("%Y-%m"),
                    start_date=s_date,
                    end_date=e_date,
                    total_revenue=random.uniform(5000, 15000),
                    total_commission=random.uniform(500, 1500),
                    platform_fee=random.uniform(100, 500),
                    net_payable=random.uniform(400, 1000),
                    status="paid",
                    created_at=e_date + timedelta(days=1)
                ))
        _safe_commit(db)
        print("  ✓ Settlements seeded")

        # ── 7. Seed support tickets ───────────────────────────────
        print("\n[7/10] Seeding support tickets...")
        ticket_data = [
            ("Battery not charging at Slot 5", "Station Madhapur — battery stuck in slot, not charging after 2 hours.", "technical", "high"),
            ("Incorrect commission calculation", "March payout shows 12% instead of agreed 15% rate.", "billing", "medium"),
            ("Station offline after power outage", "Gachibowli station went offline during power cut, hasn't reconnected.", "technical", "critical"),
            ("Request for additional battery stock", "Need 20 more WZU-48V units for Kukatpally station.", "general", "low"),
            ("Customer complaint — damaged battery", "Customer reported battery overheating during ride.", "technical", "critical"),
            ("Payout delay — February settlement", "February settlement still showing 'processing' status.", "billing", "high"),
            ("New station approval pending", "Applied for new station at Secunderabad 2 weeks ago, no update.", "general", "medium"),
            ("Swap kiosk screen not responding", "Touch screen at Banjara Hills station is unresponsive.", "technical", "high"),
            ("Promo code not applied at checkout", "SUMMER20 promo code rejected for a valid customer.", "billing", "low"),
            ("Request for maintenance schedule", "Need quarterly maintenance schedule for all 5 stations.", "general", "low"),
            ("Battery health report discrepancy", "Dashboard shows 95% health but physical inspection shows wear.", "technical", "medium"),
            ("Insurance renewal documents needed", "Insurance policy expiring next week, need renewal guidance.", "general", "medium"),
            ("QR code scanning failure at station", "Multiple customers reported QR scan failures at Hitech City.", "technical", "high"),
            ("Request for commission rate review", "Requesting review based on 6-month high performance.", "billing", "low"),
            ("Emergency: Station fire alarm triggered", "False alarm at Madhapur station, need technician visit.", "technical", "critical"),
        ]
        for subj, desc, cat, prio in ticket_data:
            existing = db.exec(select(SupportTicket).where(
                SupportTicket.user_id == dealer_user.id,
                SupportTicket.subject == subj,
            )).first()
            if not existing:
                status = random.choice([TicketStatus.OPEN, TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED])
                created = NOW - timedelta(days=random.randint(0, 30), hours=random.randint(0, 12))
                ticket = SupportTicket(
                    user_id=dealer_user.id,
                    subject=subj,
                    description=desc,
                    category=cat,
                    priority=TicketPriority(prio),
                    status=status,
                    created_at=created,
                    resolved_at=created + timedelta(hours=random.randint(2, 48)) if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED) else None,
                )
                db.add(ticket)
                db.commit()
                db.refresh(ticket)

                # Add initial message
                db.add(TicketMessage(
                    ticket_id=ticket.id,
                    sender_id=dealer_user.id,
                    message=desc,
                    created_at=created,
                ))
                # Add reply if resolved
                if status in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED):
                    db.add(TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=dealer_user.id,  # In reality would be support agent
                        message="Thank you for reporting. Our team is looking into this and will update you shortly.",
                        is_internal_note=False,
                        created_at=created + timedelta(hours=1),
                    ))
                db.commit()
        print(f"  ✓ {len(ticket_data)} tickets seeded")

        # ── 8. Seed dealer promotions / campaigns ─────────────────
        print("\n[8/10] Seeding campaigns...")
        campaigns = [
            ("Summer Swap Fest", "Flat 20% off on first 3 swaps", "SUMMER20", "PERCENTAGE", 20.0, NOW - timedelta(days=15), NOW + timedelta(days=15), True),
            ("Weekend Warrior", "₹50 off every weekend swap", "WKND50", "FIXED_AMOUNT", 50.0, NOW - timedelta(days=30), NOW, True),
            ("New User Welcome", "Free first swap for new users", "NEWUSER", "PERCENTAGE", 100.0, NOW + timedelta(days=1), NOW + timedelta(days=31), True),
            ("Monsoon Special", "15% off during monsoon season", "RAIN15", "PERCENTAGE", 15.0, NOW - timedelta(days=90), NOW - timedelta(days=30), False),
            ("Loyalty Bonus", "₹100 cashback after 10 swaps", "LOYAL100", "FIXED_AMOUNT", 100.0, NOW - timedelta(days=5), NOW + timedelta(days=55), True),
            ("Fleet Partner Deal", "25% off for fleet operators", "FLEET25", "PERCENTAGE", 25.0, NOW + timedelta(days=10), NOW + timedelta(days=70), True),
        ]
        for name, desc, code, d_type, d_val, start, end, active in campaigns:
            existing = db.exec(select(DealerPromotion).where(DealerPromotion.promo_code == code)).first()
            if not existing:
                db.add(DealerPromotion(
                    dealer_id=dealer.id,
                    name=name, description=desc, promo_code=code,
                    discount_type=d_type, discount_value=d_val,
                    min_purchase_amount=100 if d_type == "FIXED_AMOUNT" else None,
                    max_discount_amount=500 if d_type == "PERCENTAGE" else None,
                    budget_limit=random.uniform(10000, 50000),
                    usage_limit_total=random.randint(500, 5000),
                    usage_count=random.randint(0, 1500) if active else random.randint(1000, 3000),
                    total_discount_given=random.uniform(5000, 30000),
                    start_date=start, end_date=end,
                    is_active=active,
                    requires_approval=False,
                ))
        _safe_commit(db)
        print(f"  ✓ {len(campaigns)} campaigns seeded")

        # ── 9. Seed documents ─────────────────────────────────────
        print("\n[9/10] Seeding documents...")
        doc_configs = [
            ("GST_CERTIFICATE", "verification", "VERIFIED", NOW + timedelta(days=365)),
            ("PAN_CARD", "verification", "VERIFIED", None),
            ("BUSINESS_LICENSE", "business", "VERIFIED", NOW + timedelta(days=180)),
            ("INSURANCE_POLICY", "insurance", "PENDING", NOW + timedelta(days=7)),
            ("CANCELLED_CHEQUE", "verification", "VERIFIED", None),
            ("ADDRESS_PROOF", "verification", "VERIFIED", None),
            ("SAFETY_CERTIFICATE", "operational", "PENDING", NOW + timedelta(days=90)),
            ("ELECTRICAL_COMPLIANCE", "operational", "VERIFIED", NOW + timedelta(days=365)),
        ]
        for doc_type, cat, status, valid_until in doc_configs:
            existing = db.exec(select(DealerDocument).where(
                DealerDocument.dealer_id == dealer.id,
                DealerDocument.document_type == doc_type,
            )).first()
            if not existing:
                db.add(DealerDocument(
                    dealer_id=dealer.id,
                    document_type=doc_type,
                    category=cat,
                    file_url=f"https://storage.wezu.com/docs/{dealer.id}/{doc_type.lower()}_v1.pdf",
                    version=1,
                    status=status,
                    valid_until=valid_until,
                    is_verified=status == "VERIFIED",
                ))
        _safe_commit(db)
        print(f"  ✓ {len(doc_configs)} documents seeded")

        # ── 10. Seed notifications ────────────────────────────────
        print("\n[10/10] Seeding notifications...")
        notif_templates = [
            ("alert", "Low Stock Alert: WZU-48V/30Ah", "Only 5 units remaining at Madhapur SwapHub. Reorder recommended."),
            ("alert", "Maintenance Due: Gachibowli Station", "Routine maintenance overdue by 5 days. Schedule service visit."),
            ("info", "Battery Swap Completed", "Customer Ravi Sharma returned battery at Kukatpally Power Center."),
            ("promo", "Campaign Performance Update", "Summer Swap Fest has 1,240 redemptions. Revenue impact: ₹18,600."),
            ("info", "Commission Payout Processed", "₹12,450 credited to your bank account for March 2026 settlement."),
            ("alert", "Ticket Escalated: #TKT-003", "Station offline ticket escalated to critical priority."),
            ("info", "New Customer Registered", "Deepa Krishnan registered via your Banjara Hills station."),
            ("alert", "Insurance Expiring Soon", "Your insurance policy expires in 7 days. Upload renewal document."),
            ("info", "Monthly Report Ready", "Your March 2026 performance report is ready for download."),
            ("promo", "New Campaign: Loyalty Bonus", "₹100 cashback campaign is now live. Share with your customers."),
            ("alert", "Station Heartbeat Lost", "Hitech City Hub hasn't sent heartbeat in 45 minutes."),
            ("info", "Battery Health Check Complete", "15 batteries inspected. 2 flagged for replacement."),
            ("info", "Staff User Activated", "Station Manager A account is now active."),
            ("alert", "Revenue Drop Alert", "Today's revenue is 30% below the 7-day average."),
            ("info", "Document Verified", "Your GST Certificate has been verified successfully."),
            ("promo", "Weekend Warrior Results", "890 redemptions this month. Great performance!"),
            ("info", "Successful Swap", "Battery WZU-BAT-0012 swapped at Madhapur SwapHub."),
            ("alert", "Critical Ticket Update", "Emergency ticket #TKT-015 updated — technician dispatched."),
            ("info", "Payout Schedule Changed", "Your payout schedule is now Weekly (Monday). Updated per request."),
            ("info", "New Station Approved", "Kukatpally Power Center has been approved and is now operational."),
            ("alert", "Battery Overheating Reported", "Customer reported overheating for battery WZU-BAT-0025."),
            ("info", "QR Code Regenerated", "QR codes for Banjara Hills Station have been regenerated."),
            ("promo", "Fleet Partner Deal Launch", "25% off campaign for fleet operators starts in 10 days."),
            ("info", "System Maintenance", "WEZU platform maintenance scheduled for Apr 5, 2-4 AM IST."),
            ("alert", "Low Revenue Station", "Banjara Hills station revenue is 40% below target this month."),
        ]
        for n_type, title, msg in notif_templates:
            is_read = random.random() < 0.4
            db.add(Notification(
                user_id=dealer_user.id,
                title=title,
                message=msg,
                type=n_type,
                channel="push",
                status="sent",
                is_read=is_read,
                created_at=NOW - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23), minutes=random.randint(0, 59)),
            ))
        _safe_commit(db)
        print(f"  ✓ {len(notif_templates)} notifications seeded")

        # ── Seed maintenance records ─────────────────────────
        print("\nSeeding maintenance records...")
        maint_types = ["preventive", "corrective", "inspection", "emergency"]
        for st in stations:
            for _ in range(random.randint(2, 5)):
                db.add(MaintenanceRecord(
                    entity_type="station",
                    entity_id=st.id,
                    technician_id=dealer_user.id,
                    maintenance_type=random.choice(maint_types),
                    description=random.choice([
                        "Routine quarterly inspection",
                        "Slot connector replacement",
                        "Power supply unit calibration",
                        "Fire safety check",
                        "Software firmware update",
                        "Cooling system maintenance",
                    ]),
                    cost=random.uniform(500, 5000),
                    status=random.choice(["completed", "completed", "scheduled", "in_progress"]),
                    performed_at=NOW - timedelta(days=random.randint(1, 90)),
                ))
        _safe_commit(db)
        print(f"  ✓ Maintenance records seeded")

        print("\n" + "=" * 60)
        print("✅ All dealer portal data seeded successfully!")
        print("=" * 60)


if __name__ == "__main__":
    seed_all()
