"""
═══════════════════════════════════════════════════════════════
WEZU Dealer Portal — Dynamic Station Data Seeder (v2)
═══════════════════════════════════════════════════════════════
Seeds ALL data required for the dealer stations module:

  Laxman's 2 Stations:
    - Kakinada Station: 120 batteries, 89 rented, 50 swaps, ~40 reviews
    - Gollapudi Station: 100 batteries, 79 rented, 35 swaps, ~30 reviews

  Named customers appear FIRST in rental lists:
    Kakinada:  Laxman, Ammulu, Hima, Bindu, Sai, Nanda, Fayaz, Mohith, Ramya, Pratima
    Gollapudi: Laxman, Ammulu, Hima, Bindu

Run:  cd backend && python scripts/seed_stations_dynamic.py
"""

import os
import sys
import random
import uuid
from datetime import datetime, UTC, timedelta

_SEED_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")
SEED_TAG = "seed_stations_v2"  # Used in battery.notes for idempotent cleanup

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select, func
from sqlalchemy import text
from app.db.session import engine
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.battery import Battery, BatteryStatus, BatteryHealth, LocationType
from app.models.rental import Rental, RentalStatus
from app.models.swap import SwapSession
from app.models.review import Review
from app.models.maintenance import MaintenanceRecord
from app.models.financial import Wallet
from app.core.security import get_password_hash

import app.models.all  # Force load all models

NOW = datetime.now(UTC)

# ══════════════════════════════════════════════════════════════
# NAMED CUSTOMERS — these will appear at the TOP of rental lists
# ══════════════════════════════════════════════════════════════
KAKINADA_NAMED_CUSTOMERS = [
    {"full_name": "Laxman Kumar",    "phone": "9000100001", "email": "laxman.k@wezutest.com"},
    {"full_name": "Ammulu Devi",     "phone": "9000100002", "email": "ammulu.d@wezutest.com"},
    {"full_name": "Hima Bindu",      "phone": "9000100003", "email": "hima.b@wezutest.com"},
    {"full_name": "Bindu Madhavi",   "phone": "9000100004", "email": "bindu.m@wezutest.com"},
    {"full_name": "Sai Krishna",     "phone": "9000100005", "email": "sai.k@wezutest.com"},
    {"full_name": "Nanda Kishore",   "phone": "9000100006", "email": "nanda.k@wezutest.com"},
    {"full_name": "Fayaz Khan",      "phone": "9000100007", "email": "fayaz.k@wezutest.com"},
    {"full_name": "Mohith Reddy",    "phone": "9000100008", "email": "mohith.r@wezutest.com"},
    {"full_name": "Ramya Sri",       "phone": "9000100009", "email": "ramya.s@wezutest.com"},
    {"full_name": "Pratima Devi",    "phone": "9000100010", "email": "pratima.d@wezutest.com"},
]

GOLLAPUDI_NAMED_CUSTOMERS = [
    {"full_name": "Laxman Rao",     "phone": "9000200001", "email": "laxman.r@wezutest.com"},
    {"full_name": "Ammulu Priya",   "phone": "9000200002", "email": "ammulu.p@wezutest.com"},
    {"full_name": "Hima Vathi",     "phone": "9000200003", "email": "hima.v@wezutest.com"},
    {"full_name": "Bindu Priya",    "phone": "9000200004", "email": "bindu.p@wezutest.com"},
]

# ── Indian Names Pool (for generic customers) ──────────────────
FIRST_NAMES_MALE = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Mohammed",
    "Sai", "Arnav", "Dhruv", "Kabir", "Ritvik", "Shaurya",
    "Ayaan", "Krishna", "Ishaan", "Atharv", "Rohan", "Karan",
    "Vikram", "Rajesh", "Suresh", "Ramesh", "Mahesh", "Ganesh",
    "Pranav", "Nikhil", "Akash", "Ankit", "Rahul", "Amit", "Deepak",
    "Manish", "Ravi", "Sachin", "Vikas", "Ajay", "Vijay", "Sanjay",
    "Pradeep", "Naveen", "Harish", "Dinesh", "Lokesh", "Yogesh",
    "Mukesh", "Rakesh", "Pankaj", "Gaurav",
]
FIRST_NAMES_FEMALE = [
    "Saanvi", "Aanya", "Aadhya", "Aaradhya", "Ananya", "Pari", "Diya",
    "Myra", "Sara", "Ira", "Anika", "Priya", "Neha", "Sneha",
    "Kavita", "Anjali", "Pooja", "Deepa", "Meera", "Nandini",
    "Swati", "Rashmi", "Divya", "Shreya", "Tanvi", "Riya", "Sonal",
    "Komal", "Jyoti", "Lakshmi", "Radha", "Geeta", "Seema", "Sunita",
    "Rekha", "Padma", "Savita", "Usha", "Asha", "Nisha",
    "Pallavi", "Shweta", "Aishwarya", "Bhavna", "Chitra", "Heena",
    "Isha", "Juhi", "Kajal", "Lavanya",
]
LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Reddy", "Kumar", "Gupta", "Malhotra",
    "Nair", "Krishnan", "Iyer", "Rao", "Verma", "Joshi", "Mishra",
    "Agarwal", "Mehta", "Shah", "Das", "Bose", "Mukherjee",
    "Banerjee", "Chatterjee", "Sen", "Roy", "Ghosh", "Pillai",
    "Menon", "Shetty", "Kulkarni", "Deshmukh", "Patil", "Jadhav",
    "Chavan", "Pawar", "Thakur", "Chauhan", "Tiwari", "Pandey",
    "Dubey", "Srivastava", "Saxena", "Tripathi", "Dwivedi", "Bhatt",
    "Kaur", "Gill", "Dhillon", "Sandhu", "Bhatia", "Kapoor",
]

REVIEW_COMMENTS_POSITIVE = [
    "Excellent service! Battery swap was super quick and the staff was very helpful.",
    "Very convenient location. The battery was fully charged and ready to go.",
    "Smooth experience. Got my battery swapped in under 3 minutes!",
    "Best swap station in the area. Clean, well-maintained, and fast.",
    "Great station! The automated system works flawlessly.",
    "Impressed with the speed of service. Will definitely come back.",
    "Perfect! Battery was at 100% charge. Very reliable station.",
    "Friendly staff and very quick turnaround. Highly recommend!",
    "The station is very well maintained. Battery quality is excellent.",
    "Love the 24/7 availability. Swapped my battery at 11 PM without any issues.",
    "One of the best swap stations I've used. Professional and efficient.",
    "Battery health was excellent. Charges last longer from this station.",
    "Quick, easy, and affordable. What more can you ask for?",
    "The QR scan worked perfectly. In and out in 2 minutes.",
    "Very reliable station. Never had a bad experience here.",
]
REVIEW_COMMENTS_NEUTRAL = [
    "Decent service. Nothing extraordinary but gets the job done.",
    "Average experience. Wait time was a bit long today.",
    "Good station but could use better signage for first-time users.",
    "Battery was okay, charged to about 85%. Expected 100%.",
    "Service is fine but the location is a bit hard to find.",
    "Decent station. Would be great if they had more charging slots.",
]
REVIEW_COMMENTS_NEGATIVE = [
    "Had to wait 20 minutes for a slot. Needs more capacity.",
    "Battery was only 70% charged. Not acceptable for the price.",
    "One of the slots was malfunctioning. Lost 15 minutes.",
    "Staff was unhelpful when I had an issue with the QR code.",
]
DEALER_REPLIES = [
    "Thank you for your feedback! We're glad you had a great experience.",
    "We appreciate your kind words. See you again soon!",
    "Thank you for choosing our station. We strive for the best service.",
    "We're sorry for the inconvenience. We're working on improvements.",
    "Thank you for the feedback. We've noted your suggestions.",
    "We apologize for the wait. We're adding more slots to handle peak hours.",
]


def _generate_name(i):
    if i % 2 == 0:
        first = FIRST_NAMES_MALE[i % len(FIRST_NAMES_MALE)]
    else:
        first = FIRST_NAMES_FEMALE[i % len(FIRST_NAMES_FEMALE)]
    last = LAST_NAMES[i % len(LAST_NAMES)]
    suffix = f" {chr(65 + (i // 2500))}" if i >= 2500 else ""
    return f"{first} {last}{suffix}"


def _generate_phone(i):
    prefix = random.choice(["70", "72", "73", "74", "75", "76", "77", "78", "79",
                             "80", "81", "82", "83", "84", "85", "86", "87", "88",
                             "89", "90", "91", "92", "93", "94", "95", "96", "97",
                             "98", "99"])
    return f"{prefix}{10000000 + i:08d}"


def cleanup_previous_data():
    print("\n[0/10] Cleaning up stale data from previous seeds...")
    with engine.begin() as conn:
        # 0a: Cleanup batteries tagged from previous seed runs
        for tag in [SEED_TAG, "seed_laxman_script", "seed_stations_dynamic"]:
            bat_ids_rows = conn.execute(text(
                "SELECT id FROM batteries WHERE notes = :tag"
            ), {"tag": tag}).fetchall()
            bat_ids = [r[0] for r in bat_ids_rows]

            if not bat_ids:
                continue

            bat_count = len(bat_ids)
            bat_ids_str = ",".join(str(i) for i in bat_ids)

            # Delete swap sessions referencing these batteries
            conn.execute(text(f"DELETE FROM swap_sessions WHERE old_battery_id IN ({bat_ids_str}) OR new_battery_id IN ({bat_ids_str})"))
            # Get rental IDs for review cleanup
            rental_ids_rows = conn.execute(text(f"SELECT id FROM rentals WHERE battery_id IN ({bat_ids_str})")).fetchall()
            rental_ids = [r[0] for r in rental_ids_rows]
            if rental_ids:
                rental_ids_str = ",".join(str(i) for i in rental_ids)
                conn.execute(text(f"DELETE FROM reviews WHERE rental_id IN ({rental_ids_str})"))
                conn.execute(text(f"DELETE FROM rentals WHERE id IN ({rental_ids_str})"))
            # Clear slot references
            conn.execute(text(f"UPDATE station_slots SET battery_id = NULL, status = 'empty' WHERE battery_id IN ({bat_ids_str})"))
            # Delete batteries
            conn.execute(text(f"DELETE FROM batteries WHERE id IN ({bat_ids_str})"))
            print(f"  ✓ Cleaned {bat_count} batteries tagged '{tag}'")

        # 0b: Cleanup data from old/renamed stations
        old_station_names_list = ["kakinda station", "golapudi sttaion", "Madhapur SwapHub", "Gachibowli EnergyPoint"]
        names_sql = ",".join(f"'{n}'" for n in old_station_names_list)
        old_station_ids_rows = conn.execute(text(
            f"SELECT id FROM stations WHERE name IN ({names_sql})"
        )).fetchall()
        old_station_ids = [r[0] for r in old_station_ids_rows]

        if old_station_ids:
            ids_str = ",".join(str(i) for i in old_station_ids)
            # Delete reviews, swaps, rentals
            conn.execute(text(f"DELETE FROM reviews WHERE station_id IN ({ids_str})"))
            conn.execute(text(f"DELETE FROM swap_sessions WHERE station_id IN ({ids_str})"))
            conn.execute(text(f"DELETE FROM rentals WHERE start_station_id IN ({ids_str})"))
            # Get battery IDs, clear slots, delete batteries
            ob_rows = conn.execute(text(f"SELECT id FROM batteries WHERE station_id IN ({ids_str})")).fetchall()
            ob_ids = [r[0] for r in ob_rows]
            if ob_ids:
                ob_str = ",".join(str(i) for i in ob_ids)
                conn.execute(text(f"UPDATE station_slots SET battery_id = NULL, status = 'empty' WHERE battery_id IN ({ob_str})"))
                conn.execute(text(f"DELETE FROM batteries WHERE id IN ({ob_str})"))
            # Delete maintenance records
            conn.execute(text(f"DELETE FROM maintenance_records WHERE entity_type = 'station' AND entity_id IN ({ids_str})"))
        print(f"  ✓ Cleaned data from {len(old_station_ids)} old stations")

def seed_dynamic():
    print("=" * 70)
    print("  WEZU Dealer Portal — Dynamic Station Data Seeder v2")
    print("=" * 70)
    
    cleanup_previous_data()

    with Session(engine) as db:

        # ════════════════════════════════════════════════════════
        # STEP 1: Ensure dealer user + profile
        # ════════════════════════════════════════════════════════
        print("\n[1/10] Ensuring dealer user...")
        dealer_user = db.exec(select(User).where(User.email == "dealer@wezu.com")).first()
        if not dealer_user:
            dealer_user = User(
                email="dealer@wezu.com",
                phone_number="8888888888",
                full_name="Laxman Kumar",
                hashed_password=get_password_hash(_SEED_PASSWORD),
                user_type=UserType.DEALER,
                status=UserStatus.ACTIVE,
            )
            db.add(dealer_user)
            db.commit()
            db.refresh(dealer_user)
            print(f"  ✓ Created dealer user id={dealer_user.id}")
        else:
            print(f"  ✓ Dealer user exists id={dealer_user.id}")

        dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == dealer_user.id)).first()
        if not dealer:
            dealer = DealerProfile(
                user_id=dealer_user.id,
                business_name="Laxman Energy Solutions",
                contact_person="Laxman Kumar",
                contact_email="dealer@wezu.com",
                contact_phone="8888888888",
                address_line1="Plot 42, Main Road",
                city="Kakinada",
                state="Andhra Pradesh",
                pincode="533001",
                gst_number="37AABCU9603R1ZM",
                pan_number="AABCU9603R",
                is_active=True,
            )
            db.add(dealer)
            db.commit()
            db.refresh(dealer)
            print(f"  ✓ Created dealer profile id={dealer.id}")
        else:
            print(f"  ✓ Dealer profile exists id={dealer.id}")

        # ════════════════════════════════════════════════════════
        # STEP 2: Unlink phantom stations & fix names
        # ════════════════════════════════════════════════════════
        print("\n[2/10] Cleaning phantom stations...")

        # Unlink any stations from this dealer that are not our target
        target_names_old = ["kakinda station", "golapudi sttaion", "Kakinada Station", "Gollapudi Station"]
        stray_stations = db.exec(select(Station).where(
            Station.dealer_id == dealer.id,
            Station.name.notin_(target_names_old),
        )).all()
        for ss in stray_stations:
            print(f"  → Unlinking stray station: '{ss.name}' (id={ss.id})")
            ss.dealer_id = None
            db.add(ss)
        if stray_stations:
            db.commit()

        # Fix station name typos
        for old_name, new_name in [("kakinda station", "Kakinada Station"), ("golapudi sttaion", "Gollapudi Station")]:
            st = db.exec(select(Station).where(Station.name == old_name)).first()
            if st:
                st.name = new_name
                db.add(st)
                print(f"  ✓ Renamed '{old_name}' → '{new_name}'")
        db.commit()

        # ════════════════════════════════════════════════════════
        # STEP 3: Create/update the 2 target stations
        # ════════════════════════════════════════════════════════
        print("\n[3/10] Setting up 2 stations...")

        station_configs = [
            {
                "name": "Kakinada Station",
                "address": "Main Road, Near RTC Complex",
                "city": "Kakinada",
                "latitude": 16.9891,
                "longitude": 82.2475,
                "total_slots": 120,
                "battery_count": 120,
                "rented_count": 89,
                "swap_count": 50,
                "review_count": 40,
                "is_24x7": True,
                "operating_hours": '{"monday":"00:00-23:59","tuesday":"00:00-23:59","wednesday":"00:00-23:59","thursday":"00:00-23:59","friday":"00:00-23:59","saturday":"00:00-23:59","sunday":"00:00-23:59"}',
            },
            {
                "name": "Gollapudi Station",
                "address": "NH-16, Near Benz Circle",
                "city": "Vijayawada",
                "latitude": 16.5366,
                "longitude": 80.5960,
                "total_slots": 100,
                "battery_count": 100,
                "rented_count": 79,
                "swap_count": 35,
                "review_count": 30,
                "is_24x7": True,
                "operating_hours": '{"monday":"00:00-23:59","tuesday":"00:00-23:59","wednesday":"00:00-23:59","thursday":"00:00-23:59","friday":"00:00-23:59","saturday":"00:00-23:59","sunday":"00:00-23:59"}',
            },
        ]

        stations = []
        for cfg in station_configs:
            st = db.exec(select(Station).where(Station.name == cfg["name"])).first()
            if not st:
                st = Station(
                    name=cfg["name"],
                    address=cfg["address"],
                    city=cfg["city"],
                    latitude=cfg["latitude"],
                    longitude=cfg["longitude"],
                    station_type="automated",
                    total_slots=cfg["total_slots"],
                    status="OPERATIONAL",
                    is_24x7=cfg["is_24x7"],
                    rating=0.0,
                    dealer_id=dealer.id,
                    available_batteries=0,
                    available_slots=0,
                    last_maintenance_date=NOW - timedelta(days=random.randint(5, 30)),
                    contact_phone="0884-2345678" if "Kakinada" in cfg["name"] else "0866-2345678",
                    operating_hours=cfg["operating_hours"],
                    last_heartbeat=NOW - timedelta(minutes=random.randint(1, 10)),
                )
                db.add(st)
                db.commit()
                db.refresh(st)
                print(f"  ✓ Created station: {st.name} (id={st.id})")
            else:
                # Update ownership and config
                st.dealer_id = dealer.id
                st.operating_hours = cfg["operating_hours"]
                st.status = "OPERATIONAL"
                st.is_24x7 = cfg["is_24x7"]
                st.total_slots = cfg["total_slots"]
                st.address = cfg["address"]
                st.city = cfg["city"]
                st.last_heartbeat = NOW - timedelta(minutes=random.randint(1, 10))
                db.add(st)
                db.commit()
                db.refresh(st)
                print(f"  ✓ Station exists: {st.name} (id={st.id}), updated config")

            # Ensure slots exist
            existing_slots = db.exec(select(func.count(StationSlot.id)).where(
                StationSlot.station_id == st.id
            )).one() or 0
            if existing_slots < cfg["total_slots"]:
                for si in range(existing_slots, cfg["total_slots"]):
                    db.add(StationSlot(
                        station_id=st.id,
                        slot_number=si + 1,
                        status="empty",
                        is_locked=True,
                    ))
                db.commit()
                print(f"    → Created {cfg['total_slots'] - existing_slots} slots")

            stations.append((st, cfg))

        # ════════════════════════════════════════════════════════
        # STEP 4: Seed NAMED customers FIRST, then generic
        # ════════════════════════════════════════════════════════
        print("\n[4/10] Seeding named + generic customers...")
        hashed_pw = get_password_hash(_SEED_PASSWORD)

        def ensure_customer(name, phone, email):
            """Create or find a customer user, return User object."""
            user = db.exec(select(User).where(User.email == email)).first()
            if not user:
                user = User(
                    email=email,
                    phone_number=phone,
                    full_name=name,
                    hashed_password=hashed_pw,
                    user_type=UserType.CUSTOMER,
                    status=UserStatus.ACTIVE,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                # Create wallet
                existing_wallet = db.exec(select(Wallet).where(Wallet.user_id == user.id)).first()
                if not existing_wallet:
                    db.add(Wallet(user_id=user.id, balance=round(random.uniform(500, 5000), 2)))
                    db.commit()
            return user

        # Named customers for Kakinada
        kakinada_named_users = []
        for c in KAKINADA_NAMED_CUSTOMERS:
            user = ensure_customer(c["full_name"], c["phone"], c["email"])
            kakinada_named_users.append(user)
            print(f"    ✓ Named: {user.full_name} (id={user.id})")

        # Named customers for Gollapudi
        gollapudi_named_users = []
        for c in GOLLAPUDI_NAMED_CUSTOMERS:
            user = ensure_customer(c["full_name"], c["phone"], c["email"])
            gollapudi_named_users.append(user)
            print(f"    ✓ Named: {user.full_name} (id={user.id})")

        # Generic customers (fill rest of ~1000)
        existing_cust_count = db.exec(
            select(func.count(User.id)).where(User.user_type == UserType.CUSTOMER)
        ).one() or 0

        generic_needed = max(0, 1000 - existing_cust_count)
        created_generic = 0
        for i in range(generic_needed):
            email = f"cust_{existing_cust_count + i:04d}@wezutest.com"
            existing = db.exec(select(User).where(User.email == email)).first()
            if existing:
                continue
            user = User(
                email=email,
                phone_number=_generate_phone(existing_cust_count + i),
                full_name=_generate_name(existing_cust_count + i),
                hashed_password=hashed_pw,
                user_type=UserType.CUSTOMER,
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            created_generic += 1
            if created_generic % 100 == 0:
                db.commit()
                print(f"    ... created {created_generic} generic customers")
        db.commit()

        # Seed wallets for all customers without one
        all_customers = db.exec(select(User).where(User.user_type == UserType.CUSTOMER)).all()
        existing_wallet_ids = set(db.exec(select(Wallet.user_id)).all())
        wallet_count = 0
        for c in all_customers:
            if c.id not in existing_wallet_ids:
                db.add(Wallet(user_id=c.id, balance=round(random.uniform(200, 5000), 2)))
                wallet_count += 1
                if wallet_count % 200 == 0:
                    db.commit()
        db.commit()

        # RELOAD customers to prevent lazy-load storm on expired objects
        all_customers = db.exec(select(User).where(User.user_type == UserType.CUSTOMER)).all()

        print(f"  ✓ {len(all_customers)} total customers ({created_generic} new, {wallet_count} new wallets)")

        # Build a pool of generic customers (exclude named ones)
        named_ids = set(u.id for u in kakinada_named_users + gollapudi_named_users)
        generic_customers = [c for c in all_customers if c.id not in named_ids]
        random.shuffle(generic_customers)

        # ════════════════════════════════════════════════════════
        # STEP 5: Seed batteries (120 + 100 = 220)
        # ════════════════════════════════════════════════════════
        print("\n[5/10] Seeding 220 batteries...")

        all_station_batteries = {}  # station_id -> list of Battery objects

        for st, cfg in stations:
            bat_count = cfg["battery_count"]
            rented_count = cfg["rented_count"]
            available_count = bat_count - rented_count

            station_bats = []
            for i in range(bat_count):
                serial = f"WZ-{st.id:02d}-{i:04d}-{uuid.uuid4().hex[:6]}"

                # FIRST rented_count batteries are RENTED, rest are AVAILABLE
                if i < rented_count:
                    status = BatteryStatus.RENTED
                    charge = round(random.uniform(30, 85), 1)
                    health = round(random.uniform(80, 100), 1)
                else:
                    status = BatteryStatus.AVAILABLE
                    charge = round(random.uniform(85, 100), 1)
                    health = round(random.uniform(85, 100), 1)

                health_enum = BatteryHealth.GOOD if health > 80 else (BatteryHealth.FAIR if health > 60 else BatteryHealth.POOR)

                bat = Battery(
                    serial_number=serial,
                    qr_code_data=f"QR-{serial}",
                    station_id=st.id,
                    status=status,
                    health_status=health_enum,
                    current_charge=charge,
                    health_percentage=health,
                    cycle_count=random.randint(10, 500),
                    battery_type="48V/30Ah",
                    manufacturer="Wezu Energy",
                    purchase_cost=round(random.uniform(8000, 15000), 2),
                    location_type=LocationType.STATION,
                    manufacture_date=NOW - timedelta(days=random.randint(90, 365)),
                    purchase_date=NOW - timedelta(days=random.randint(60, 300)),
                    last_charged_at=NOW - timedelta(hours=random.randint(1, 72)),
                    notes=SEED_TAG,
                )
                db.add(bat)
                station_bats.append(bat)

                if (i + 1) % 50 == 0:
                    db.commit()

            db.commit()

            # Refresh to get IDs
            refreshed = db.exec(select(Battery).where(
                Battery.station_id == st.id, Battery.notes == SEED_TAG
            )).all()
            all_station_batteries[st.id] = refreshed

            # Assign batteries to slots
            st_slots = db.exec(select(StationSlot).where(
                StationSlot.station_id == st.id
            ).order_by(StationSlot.slot_number)).all()
            for idx, bat in enumerate(refreshed):
                if idx < len(st_slots):
                    st_slots[idx].battery_id = bat.id
                    st_slots[idx].status = "charging" if bat.status == BatteryStatus.AVAILABLE else "occupied"
                    db.add(st_slots[idx])
            db.commit()

            print(f"  ✓ {st.name}: {len(refreshed)} batteries ({rented_count} rented, {available_count} available)")

        # ════════════════════════════════════════════════════════
        # STEP 6: Seed active rentals (89 + 79 = 168)
        # ════════════════════════════════════════════════════════
        print("\n[6/10] Seeding 168 active rentals...")

        rental_count = 0
        generic_idx = 0  # Pointer into generic_customers pool

        for st, cfg in stations:
            rented_count = cfg["rented_count"]
            rented_batteries = [b for b in all_station_batteries[st.id] if b.status == BatteryStatus.RENTED]

            # Determine named customers for this station
            if "Kakinada" in st.name:
                named_users = kakinada_named_users
            else:
                named_users = gollapudi_named_users

            for i, bat in enumerate(rented_batteries):
                # NAMED customers come FIRST
                if i < len(named_users):
                    customer = named_users[i]
                else:
                    # Use generic customers
                    if generic_idx < len(generic_customers):
                        customer = generic_customers[generic_idx]
                        generic_idx += 1
                    else:
                        customer = random.choice(all_customers)

                start_time = NOW - timedelta(
                    days=random.randint(0, 7),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )
                duration_hours = random.choice([4, 8, 12, 24, 48])

                rental = Rental(
                    user_id=customer.id,
                    battery_id=bat.id,
                    start_station_id=st.id,
                    start_time=start_time,
                    expected_end_time=start_time + timedelta(hours=duration_hours),
                    status=RentalStatus.ACTIVE,
                    total_amount=round(random.uniform(50, 500), 2),
                    security_deposit=round(random.uniform(100, 500), 2),
                    late_fee=0.0 if random.random() > 0.15 else round(random.uniform(20, 100), 2),
                    start_battery_level=round(random.uniform(80, 100), 1),
                    currency="INR",
                )
                db.add(rental)
                rental_count += 1

                if rental_count % 50 == 0:
                    db.commit()

        # Also seed some completed rentals for history
        completed_count = 0
        for i in range(50):
            st, cfg = random.choice(stations)
            customer = random.choice(all_customers)
            avail_bat = random.choice([b for b in all_station_batteries[st.id] if b.status == BatteryStatus.AVAILABLE][:5]) if [b for b in all_station_batteries[st.id] if b.status == BatteryStatus.AVAILABLE] else None
            if not avail_bat:
                continue

            start_time = NOW - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))
            end_time = start_time + timedelta(hours=random.randint(2, 48))

            rental = Rental(
                user_id=customer.id,
                battery_id=avail_bat.id,
                start_station_id=st.id,
                end_station_id=random.choice([s.id for s, _ in stations]),
                start_time=start_time,
                expected_end_time=start_time + timedelta(hours=24),
                end_time=end_time,
                status=RentalStatus.COMPLETED,
                total_amount=round(random.uniform(80, 400), 2),
                security_deposit=round(random.uniform(100, 500), 2),
                late_fee=0.0 if random.random() > 0.2 else round(random.uniform(20, 80), 2),
                start_battery_level=round(random.uniform(85, 100), 1),
                end_battery_level=round(random.uniform(10, 40), 1),
                distance_traveled_km=round(random.uniform(5, 80), 1),
                is_deposit_refunded=True,
                currency="INR",
            )
            db.add(rental)
            completed_count += 1

        db.commit()
        print(f"  ✓ {rental_count} active + {completed_count} completed rentals seeded")

        # ════════════════════════════════════════════════════════
        # STEP 7: Seed swap sessions (50 + 35 = 85)
        # ════════════════════════════════════════════════════════
        print("\n[7/10] Seeding 85 swap sessions...")

        swap_count = 0
        for st, cfg in stations:
            target_swaps = cfg["swap_count"]

            # Get active rentals for this station to link swaps
            station_rentals = db.exec(select(Rental).where(
                Rental.start_station_id == st.id,
                Rental.status == RentalStatus.ACTIVE,
            )).all()

            station_bats = all_station_batteries[st.id]

            for i in range(target_swaps):
                # Pick a customer from active rentals
                if i < len(station_rentals):
                    rental = station_rentals[i]
                    customer_id = rental.user_id
                    rental_id = rental.id
                else:
                    rental = random.choice(station_rentals) if station_rentals else None
                    customer_id = rental.user_id if rental else random.choice(all_customers).id
                    rental_id = rental.id if rental else None

                # Pick two different batteries
                if len(station_bats) >= 2:
                    old_bat, new_bat = random.sample(station_bats, 2)
                else:
                    continue

                swap_time = NOW - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )

                swap = SwapSession(
                    rental_id=rental_id,
                    user_id=customer_id,
                    station_id=st.id,
                    old_battery_id=old_bat.id,
                    new_battery_id=new_bat.id,
                    old_battery_soc=round(random.uniform(5, 25), 1),
                    new_battery_soc=round(random.uniform(85, 100), 1),
                    swap_amount=round(random.uniform(30, 80), 2),
                    currency="INR",
                    status="completed",
                    payment_status="paid",
                    created_at=swap_time,
                    completed_at=swap_time + timedelta(minutes=random.randint(2, 8)),
                )
                db.add(swap)
                swap_count += 1

                if swap_count % 20 == 0:
                    db.commit()

        db.commit()
        print(f"  ✓ {swap_count} swap sessions seeded")

        # ════════════════════════════════════════════════════════
        # STEP 8: Seed reviews (40 + 30 = 70)
        # ════════════════════════════════════════════════════════
        print("\n[8/10] Seeding 70 reviews...")

        review_count = 0
        used_review_keys = set()

        for st, cfg in stations:
            target_reviews = cfg["review_count"]

            # Named customers get reviews first
            if "Kakinada" in st.name:
                priority_users = kakinada_named_users
            else:
                priority_users = gollapudi_named_users

            for i in range(target_reviews):
                # Pick customer: named users first, then generic
                if i < len(priority_users):
                    customer = priority_users[i]
                else:
                    # Pick a unique customer for this station
                    customer = None
                    for _ in range(50):
                        c = random.choice(all_customers)
                        key = (c.id, st.id)
                        if key not in used_review_keys:
                            customer = c
                            used_review_keys.add(key)
                            break
                    if customer is None:
                        customer = random.choice(all_customers)

                used_review_keys.add((customer.id, st.id))

                # Weighted rating: mostly 4-5 stars
                rating = random.choices([5, 4, 3, 2, 1], weights=[40, 35, 15, 7, 3])[0]

                if rating >= 4:
                    comment = random.choice(REVIEW_COMMENTS_POSITIVE)
                elif rating == 3:
                    comment = random.choice(REVIEW_COMMENTS_NEUTRAL)
                else:
                    comment = random.choice(REVIEW_COMMENTS_NEGATIVE)

                # Link to rental if possible
                rental = db.exec(select(Rental).where(
                    Rental.user_id == customer.id,
                    Rental.start_station_id == st.id,
                ).limit(1)).first()

                response = None
                if random.random() < 0.4:
                    response = random.choice(DEALER_REPLIES)

                review = Review(
                    user_id=customer.id,
                    station_id=st.id,
                    rental_id=rental.id if rental else None,
                    rating=rating,
                    comment=comment,
                    response_from_station=response,
                    is_verified_rental=rental is not None,
                    created_at=NOW - timedelta(
                        days=random.randint(0, 45),
                        hours=random.randint(0, 23),
                    ),
                )
                db.add(review)
                review_count += 1

                if review_count % 20 == 0:
                    db.commit()

        db.commit()
        print(f"  ✓ {review_count} reviews seeded")

        # ════════════════════════════════════════════════════════
        # STEP 9: Update station ratings + battery counts
        # ════════════════════════════════════════════════════════
        print("\n[9/10] Computing station ratings & battery counts...")

        for st, cfg in stations:
            # Rating
            avg_rating = db.exec(
                select(func.avg(Review.rating)).where(Review.station_id == st.id)
            ).one()
            rev_count = db.exec(
                select(func.count(Review.id)).where(Review.station_id == st.id)
            ).one() or 0

            if avg_rating:
                st.rating = round(float(avg_rating), 1)
                st.total_reviews = rev_count

            # Battery counts
            avail = db.exec(select(func.count(Battery.id)).where(
                Battery.station_id == st.id, Battery.status == BatteryStatus.AVAILABLE
            )).one() or 0
            total_bats = db.exec(select(func.count(Battery.id)).where(
                Battery.station_id == st.id
            )).one() or 0

            st.available_batteries = avail
            st.available_slots = max(0, st.total_slots - total_bats)
            db.add(st)
            print(f"  ✓ {st.name}: rating={st.rating} ({rev_count} reviews), {avail}/{total_bats} batteries available")

        db.commit()

        # ════════════════════════════════════════════════════════
        # STEP 10: Seed maintenance records
        # ════════════════════════════════════════════════════════
        print("\n[10/10] Seeding maintenance records...")

        maint_descriptions = [
            "Routine quarterly inspection and cleaning",
            "Slot connector replacement — ports 3 & 7",
            "Power supply unit calibration",
            "Fire safety check and certification",
            "Software firmware update to v3.2.1",
            "Cooling system fan replacement",
            "UPS battery backup testing",
            "QR scanner recalibration",
            "Electrical wiring inspection",
            "Emergency power shutdown test",
        ]

        for st, _ in stations:
            existing_maint = db.exec(select(func.count(MaintenanceRecord.id)).where(
                MaintenanceRecord.entity_type == "station",
                MaintenanceRecord.entity_id == st.id,
            )).one() or 0

            if existing_maint >= 5:
                print(f"  ✓ {st.name}: {existing_maint} records exist, skipping")
                continue

            for j in range(random.randint(4, 8)):
                db.add(MaintenanceRecord(
                    entity_type="station",
                    entity_id=st.id,
                    technician_id=dealer_user.id,
                    maintenance_type=random.choice(["preventive", "corrective", "inspection", "emergency"]),
                    description=random.choice(maint_descriptions),
                    cost=round(random.uniform(500, 8000), 2),
                    status=random.choice(["completed", "completed", "completed", "scheduled", "in_progress"]),
                    performed_at=NOW - timedelta(days=random.randint(1, 90)),
                ))
            db.commit()
            print(f"  ✓ {st.name}: maintenance records seeded")

        # ════════════════════════════════════════════════════════
        # FINAL: Print verification summary
        # ════════════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("  ✅ SEEDING COMPLETE — VERIFICATION")
        print("=" * 70)

        total_customers = db.exec(
            select(func.count(User.id)).where(User.user_type == UserType.CUSTOMER)
        ).one()

        for st, cfg in stations:
            total_batt = db.exec(select(func.count(Battery.id)).where(Battery.station_id == st.id)).one()
            avail_batt = db.exec(select(func.count(Battery.id)).where(
                Battery.station_id == st.id, Battery.status == BatteryStatus.AVAILABLE
            )).one()
            rented_batt = db.exec(select(func.count(Battery.id)).where(
                Battery.station_id == st.id, Battery.status == BatteryStatus.RENTED
            )).one()
            active_rentals = db.exec(select(func.count(Rental.id)).where(
                Rental.start_station_id == st.id, Rental.status == RentalStatus.ACTIVE
            )).one()
            swaps = db.exec(select(func.count(SwapSession.id)).where(
                SwapSession.station_id == st.id
            )).one()
            reviews = db.exec(select(func.count(Review.id)).where(Review.station_id == st.id)).one()

            # Print first 5 rental customers to verify named ones are first
            first_rentals = db.exec(select(Rental).where(
                Rental.start_station_id == st.id,
                Rental.status == RentalStatus.ACTIVE,
            ).order_by(Rental.id).limit(5)).all()
            first_names = []
            for r in first_rentals:
                u = db.get(User, r.user_id)
                first_names.append(u.full_name if u else "?")

            print(f"\n  📍 {st.name} (id={st.id})")
            print(f"     Batteries: {total_batt} total | {avail_batt} available | {rented_batt} rented")
            print(f"     Active Rentals: {active_rentals} (target: {cfg['rented_count']})")
            print(f"     Swaps: {swaps} (target: {cfg['swap_count']})")
            print(f"     Reviews: {reviews} (target: {cfg['review_count']}) | Rating: {st.rating}")
            print(f"     First 5 renters: {', '.join(first_names)}")

        print(f"\n  👥 Total Customers: {total_customers}")
        print("=" * 70)


if __name__ == "__main__":
    seed_dynamic()
