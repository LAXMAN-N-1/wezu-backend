"""
═══════════════════════════════════════════════════════════════
WEZU Dealer Portal — Dynamic Station Data Seeder
═══════════════════════════════════════════════════════════════
Seeds ALL data required for the stations module to be fully dynamic:
  - 1000 customer users with wallets
  - 2 stations (100 + 120 batteries = 220 total)
  - 180 active rentals (80 from Station 1, 100 from Station 2)
  - 60 completed swap sessions
  - 120 customer reviews
  - Maintenance records for both stations

Run:  cd backend && python scripts/seed_stations_dynamic.py
"""

import os
import sys
import random
import uuid
from datetime import datetime, UTC, timedelta

_SEED_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlmodel import Session, select, func
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
from app.models.admin_user import AdminUser
from app.models.rbac import Role, AdminUserRole
from app.models.role_right import RoleRight
from app.core.security import get_password_hash

import app.models.all  # Force load all models to resolve SQLAlchemy mapper dependencies

NOW = datetime.now(UTC)

# ── Indian Names Pool ──────────────────────────────────────────
FIRST_NAMES_MALE = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Mohammed",
    "Sai", "Arnav", "Dhruv", "Kabir", "Ritvik", "Aayu", "Shaurya",
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


def _safe_commit(session):
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"  ⚠ Commit error: {e}")


def _generate_name(i):
    """Generate a unique full name."""
    if i % 2 == 0:
        first = FIRST_NAMES_MALE[i % len(FIRST_NAMES_MALE)]
    else:
        first = FIRST_NAMES_FEMALE[i % len(FIRST_NAMES_FEMALE)]
    last = LAST_NAMES[i % len(LAST_NAMES)]
    # Add suffix for uniqueness when we have more than ~2500 combos
    suffix = f" {chr(65 + (i // 2500))}" if i >= 2500 else ""
    return f"{first} {last}{suffix}"


def _generate_phone(i):
    """Generate unique Indian phone number."""
    prefix = random.choice(["70", "72", "73", "74", "75", "76", "77", "78", "79",
                             "80", "81", "82", "83", "84", "85", "86", "87", "88",
                             "89", "90", "91", "92", "93", "94", "95", "96", "97",
                             "98", "99"])
    return f"{prefix}{10000000 + i:08d}"


def seed_dynamic():
    with Session(engine) as db:
        print("=" * 70)
        print("  WEZU Dealer Portal — Dynamic Station Data Seeder")
        print("=" * 70)

        # ════════════════════════════════════════════════════════
        # STEP 1: Ensure dealer user + profile
        # ════════════════════════════════════════════════════════
        print("\n[1/9] Ensuring dealer user...")
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

        # ════════════════════════════════════════════════════════
        # STEP 2: Seed 1000 customer users
        # ════════════════════════════════════════════════════════
        print("\n[2/9] Seeding 1000 customers...")
        existing_customers = db.exec(
            select(User).where(User.user_type == UserType.CUSTOMER)
        ).all()
        existing_map = {u.email: u for u in existing_customers}

        customers = list(existing_customers)
        hashed_pw = get_password_hash(_SEED_PASSWORD)
        created_count = 0

        for i in range(1000):
            email = f"cust_{i:04d}@wezutest.com"
            if email in existing_map:
                continue

            full_name = _generate_name(i)
            phone = _generate_phone(i)

            user = User(
                email=email,
                phone_number=phone,
                full_name=full_name,
                hashed_password=hashed_pw,
                user_type=UserType.CUSTOMER,
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            created_count += 1

            # Batch commit every 100
            if created_count % 100 == 0:
                db.commit()
                print(f"    ... created {created_count} customers")

        if created_count % 100 != 0:
            db.commit()

        # Refresh customer list
        customers = db.exec(
            select(User).where(User.user_type == UserType.CUSTOMER)
        ).all()
        print(f"  ✓ {len(customers)} total customers ({created_count} new)")

        # Seed wallets for new customers
        print("  → Seeding wallets...")
        existing_wallet_user_ids = set(
            db.exec(select(Wallet.user_id)).all()
        )
        wallet_count = 0
        for c in customers:
            if c.id not in existing_wallet_user_ids:
                db.add(Wallet(user_id=c.id, balance=round(random.uniform(200, 5000), 2)))
                wallet_count += 1
                if wallet_count % 200 == 0:
                    db.commit()
        db.commit()
        print(f"  ✓ {wallet_count} new wallets created")

        # ════════════════════════════════════════════════════════
        # STEP 3: Seed / Update 2 Stations
        # ════════════════════════════════════════════════════════
        print("\n[3/9] Setting up 2 stations...")

        station_configs = [
            {
                "name": "Madhapur SwapHub",
                "address": "Plot 42, Madhapur IT Park",
                "city": "Hyderabad",
                "latitude": 17.4484,
                "longitude": 78.3908,
                "total_slots": 12,
                "is_24x7": True,
                "battery_count": 100,
                "rented_count": 80,
                "operating_hours": '{"monday":"06:00-22:00","tuesday":"06:00-22:00","wednesday":"06:00-22:00","thursday":"06:00-22:00","friday":"06:00-22:00","saturday":"08:00-20:00","sunday":"09:00-18:00"}',
            },
            {
                "name": "Gachibowli EnergyPoint",
                "address": "DLF Cyber City, Gachibowli",
                "city": "Hyderabad",
                "latitude": 17.4401,
                "longitude": 78.3489,
                "total_slots": 15,
                "is_24x7": True,
                "battery_count": 120,
                "rented_count": 100,
                "operating_hours": '{"monday":"00:00-23:59","tuesday":"00:00-23:59","wednesday":"00:00-23:59","thursday":"00:00-23:59","friday":"00:00-23:59","saturday":"00:00-23:59","sunday":"00:00-23:59"}',
            },
        ]

        stations = []
        for cfg in station_configs:
            st = db.exec(
                select(Station).where(
                    Station.name == cfg["name"],
                    Station.dealer_id == dealer.id,
                )
            ).first()

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
                    rating=0.0,  # Will be computed from reviews later
                    dealer_id=dealer.id,
                    available_batteries=0,  # Will be computed dynamically
                    available_slots=0,
                    last_maintenance_date=NOW - timedelta(days=random.randint(5, 30)),
                    contact_phone="040-12345678",
                    operating_hours=cfg["operating_hours"],
                    last_heartbeat=NOW - timedelta(minutes=random.randint(1, 10)),
                )
                db.add(st)
                db.commit()
                db.refresh(st)
                print(f"  ✓ Created station: {st.name} (id={st.id})")

                # Create slots
                for slot_i in range(st.total_slots):
                    slot_status = random.choice(["empty", "charging", "ready", "ready", "empty"])
                    db.add(StationSlot(
                        station_id=st.id,
                        slot_number=slot_i + 1,
                        status=slot_status,
                        is_locked=slot_status == "empty",
                        current_power_w=random.uniform(50, 500) if slot_status == "charging" else 0,
                    ))
                db.commit()
            else:
                # Update operating hours if station exists
                st.operating_hours = cfg["operating_hours"]
                st.status = "OPERATIONAL"
                db.add(st)
                db.commit()
                db.refresh(st)
                print(f"  ✓ Station exists: {st.name} (id={st.id})")

            stations.append((st, cfg))

        # ════════════════════════════════════════════════════════
        # STEP 4: Seed 220 Batteries across 2 stations
        # ════════════════════════════════════════════════════════
        print("\n[4/9] Seeding 220 batteries...")

        all_seeded_batteries = []
        for st, cfg in stations:
            existing_count = db.exec(
                select(func.count(Battery.id)).where(Battery.station_id == st.id)
            ).one() or 0

            batteries_needed = cfg["battery_count"] - existing_count
            rented_count = cfg["rented_count"]
            available_count = cfg["battery_count"] - rented_count

            if batteries_needed <= 0:
                print(f"  ✓ {st.name}: {existing_count} batteries already exist (need {cfg['battery_count']})")
                existing_batteries = db.exec(
                    select(Battery).where(Battery.station_id == st.id)
                ).all()
                all_seeded_batteries.extend([(b, st) for b in existing_batteries])
                continue

            print(f"  → Creating {batteries_needed} batteries for {st.name}...")
            for i in range(batteries_needed):
                battery_index = existing_count + i
                serial = f"WZ-{st.id:02d}-{battery_index:04d}"

                # Determine status
                if battery_index < rented_count:
                    status = BatteryStatus.RENTED
                elif battery_index < rented_count + int(available_count * 0.6):
                    status = BatteryStatus.AVAILABLE
                elif battery_index < rented_count + int(available_count * 0.85):
                    status = BatteryStatus.CHARGING
                elif battery_index < rented_count + int(available_count * 0.95):
                    status = BatteryStatus.MAINTENANCE
                else:
                    status = BatteryStatus.RETIRED

                charge = round(random.uniform(15, 100), 1) if status != BatteryStatus.RENTED else round(random.uniform(30, 85), 1)
                if status == BatteryStatus.AVAILABLE:
                    charge = round(random.uniform(85, 100), 1)
                if status == BatteryStatus.CHARGING:
                    charge = round(random.uniform(20, 70), 1)

                health = round(random.uniform(75, 100), 1)
                if status == BatteryStatus.MAINTENANCE:
                    health = round(random.uniform(50, 75), 1)
                if status == BatteryStatus.RETIRED:
                    health = round(random.uniform(20, 50), 1)

                battery = Battery(
                    serial_number=serial,
                    qr_code_data=f"QR-{serial}",
                    station_id=st.id,
                    status=status,
                    health_status=BatteryHealth.GOOD if health > 80 else (BatteryHealth.FAIR if health > 60 else BatteryHealth.POOR),
                    current_charge=charge,
                    health_percentage=health,
                    cycle_count=random.randint(10, 500),
                    battery_type="48V/30Ah",
                    manufacturer="Wezu Energy",
                    purchase_cost=round(random.uniform(8000, 15000), 2),
                    location_type=LocationType.STATION,
                    location_id=st.id,
                    manufacture_date=NOW - timedelta(days=random.randint(90, 365)),
                    purchase_date=NOW - timedelta(days=random.randint(60, 300)),
                    last_charged_at=NOW - timedelta(hours=random.randint(1, 72)),
                )
                db.add(battery)

                if (i + 1) % 50 == 0:
                    db.commit()
                    print(f"    ... {i + 1}/{batteries_needed}")

            db.commit()

            # Refresh battery list for this station
            station_batteries = db.exec(
                select(Battery).where(Battery.station_id == st.id)
            ).all()
            all_seeded_batteries.extend([(b, st) for b in station_batteries])
            print(f"  ✓ {st.name}: {len(station_batteries)} batteries total")

        # ════════════════════════════════════════════════════════
        # STEP 5: Seed 180 Active Rentals
        # ════════════════════════════════════════════════════════
        print("\n[5/9] Seeding active rentals...")

        # Check existing active rentals
        existing_active_rentals = db.exec(
            select(func.count(Rental.id)).where(
                Rental.status == RentalStatus.ACTIVE,
                Rental.start_station_id.in_([s.id for s, _ in stations]),
            )
        ).one() or 0

        if existing_active_rentals >= 150:
            print(f"  ✓ Already have {existing_active_rentals} active rentals, skipping")
        else:
            # Clear old active rentals for clean state
            old_rentals = db.exec(
                select(Rental).where(
                    Rental.status == RentalStatus.ACTIVE,
                    Rental.start_station_id.in_([s.id for s, _ in stations]),
                )
            ).all()
            for r in old_rentals:
                db.delete(r)
            db.commit()

            rental_count = 0
            used_customer_ids = set()
            used_battery_ids = set()

            for st, cfg in stations:
                rented_batteries = db.exec(
                    select(Battery).where(
                        Battery.station_id == st.id,
                        Battery.status == BatteryStatus.RENTED,
                    )
                ).all()

                for bat in rented_batteries:
                    if bat.id in used_battery_ids:
                        continue

                    # Pick a unique customer
                    customer = None
                    attempts = 0
                    while attempts < 50:
                        c = random.choice(customers)
                        if c.id not in used_customer_ids:
                            customer = c
                            used_customer_ids.add(c.id)
                            break
                        attempts += 1

                    if customer is None:
                        customer = random.choice(customers)

                    start_time = NOW - timedelta(
                        days=random.randint(0, 5),
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
                    used_battery_ids.add(bat.id)
                    rental_count += 1

                    if rental_count % 50 == 0:
                        db.commit()
                        print(f"    ... {rental_count} rentals created")

            # Also seed some completed rentals for history
            completed_count = 0
            for i in range(50):
                st, cfg = random.choice(stations)
                avail_batteries = db.exec(
                    select(Battery).where(
                        Battery.station_id == st.id,
                        Battery.status == BatteryStatus.AVAILABLE,
                    ).limit(1)
                ).first()
                if not avail_batteries:
                    continue

                customer = random.choice(customers)
                start_time = NOW - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))
                end_time = start_time + timedelta(hours=random.randint(2, 48))

                rental = Rental(
                    user_id=customer.id,
                    battery_id=avail_batteries.id,
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
        # STEP 6: Seed 60 Completed Swap Sessions
        # ════════════════════════════════════════════════════════
        print("\n[6/9] Seeding swap sessions...")

        existing_swaps = db.exec(
            select(func.count(SwapSession.id)).where(
                SwapSession.station_id.in_([s.id for s, _ in stations]),
            )
        ).one() or 0

        if existing_swaps >= 50:
            print(f"  ✓ Already have {existing_swaps} swaps, skipping")
        else:
            swap_count = 0
            # Get all rentals for linking
            all_rentals = db.exec(
                select(Rental).where(
                    Rental.start_station_id.in_([s.id for s, _ in stations]),
                )
            ).all()

            for i in range(60):
                st, _ = random.choice(stations)

                # Get batteries at this station
                station_batteries = db.exec(
                    select(Battery).where(Battery.station_id == st.id).limit(50)
                ).all()

                if len(station_batteries) < 2:
                    continue

                old_bat = random.choice(station_batteries)
                new_bat = random.choice([b for b in station_batteries if b.id != old_bat.id])
                customer = random.choice(customers)

                # Link to a rental if possible
                rental_id = None
                matching_rentals = [r for r in all_rentals if r.user_id == customer.id]
                if matching_rentals:
                    rental_id = matching_rentals[0].id

                swap_time = NOW - timedelta(
                    days=random.randint(0, 20),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )

                swap_status = random.choices(
                    ["completed", "completed", "completed", "completed", "initiated", "processing"],
                    weights=[40, 30, 15, 5, 5, 5],
                )[0]

                swap = SwapSession(
                    rental_id=rental_id,
                    user_id=customer.id,
                    station_id=st.id,
                    old_battery_id=old_bat.id,
                    new_battery_id=new_bat.id,
                    old_battery_soc=round(random.uniform(5, 25), 1),
                    new_battery_soc=round(random.uniform(85, 100), 1),
                    swap_amount=round(random.uniform(30, 80), 2),
                    currency="INR",
                    status=swap_status,
                    payment_status="paid" if swap_status == "completed" else "pending",
                    created_at=swap_time,
                    completed_at=swap_time + timedelta(minutes=random.randint(2, 8)) if swap_status == "completed" else None,
                )
                db.add(swap)
                swap_count += 1

                if swap_count % 20 == 0:
                    db.commit()

            db.commit()
            print(f"  ✓ {swap_count} swap sessions seeded")

        # ════════════════════════════════════════════════════════
        # STEP 7: Seed 120 Reviews
        # ════════════════════════════════════════════════════════
        print("\n[7/9] Seeding reviews...")

        existing_reviews = db.exec(
            select(func.count(Review.id)).where(
                Review.station_id.in_([s.id for s, _ in stations]),
            )
        ).one() or 0

        if existing_reviews >= 100:
            print(f"  ✓ Already have {existing_reviews} reviews, skipping")
        else:
            review_count = 0
            used_review_customers = set()

            for i in range(120):
                st, _ = random.choice(stations)

                # Pick a customer we haven't used for this station
                customer = None
                for _ in range(50):
                    c = random.choice(customers)
                    key = (c.id, st.id)
                    if key not in used_review_customers:
                        customer = c
                        used_review_customers.add(key)
                        break

                if customer is None:
                    customer = random.choice(customers)

                # Weighted rating: mostly 4-5
                rating = random.choices([5, 4, 3, 2, 1], weights=[40, 30, 15, 10, 5])[0]

                if rating >= 4:
                    comment = random.choice(REVIEW_COMMENTS_POSITIVE)
                elif rating == 3:
                    comment = random.choice(REVIEW_COMMENTS_NEUTRAL)
                else:
                    comment = random.choice(REVIEW_COMMENTS_NEGATIVE)

                # Link to a rental if we can find one
                rental = db.exec(
                    select(Rental).where(
                        Rental.user_id == customer.id,
                        Rental.start_station_id == st.id,
                    ).limit(1)
                ).first()

                response = None
                if random.random() < 0.4:  # 40% have dealer replies
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

                if review_count % 30 == 0:
                    db.commit()

            db.commit()
            print(f"  ✓ {review_count} reviews seeded")

        # ════════════════════════════════════════════════════════
        # STEP 8: Update station ratings from actual reviews
        # ════════════════════════════════════════════════════════
        print("\n[8/9] Computing station ratings from reviews...")

        for st, _ in stations:
            avg_rating = db.exec(
                select(func.avg(Review.rating)).where(Review.station_id == st.id)
            ).one()
            review_count = db.exec(
                select(func.count(Review.id)).where(Review.station_id == st.id)
            ).one() or 0

            if avg_rating:
                st.rating = round(float(avg_rating), 1)
                st.total_reviews = review_count
                db.add(st)
                print(f"  ✓ {st.name}: rating={st.rating} ({review_count} reviews)")

        db.commit()

        # ════════════════════════════════════════════════════════
        # STEP 9: Seed Maintenance Records
        # ════════════════════════════════════════════════════════
        print("\n[9/9] Seeding maintenance records...")

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
            existing_maint = db.exec(
                select(func.count(MaintenanceRecord.id)).where(
                    MaintenanceRecord.entity_type == "station",
                    MaintenanceRecord.entity_id == st.id,
                )
            ).one() or 0

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
        # FINAL: Print Summary
        # ════════════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("  ✅ SEEDING COMPLETE — VERIFICATION")
        print("=" * 70)

        total_customers = db.exec(
            select(func.count(User.id)).where(User.user_type == UserType.CUSTOMER)
        ).one()

        for st, cfg in stations:
            total_batt = db.exec(
                select(func.count(Battery.id)).where(Battery.station_id == st.id)
            ).one()
            avail_batt = db.exec(
                select(func.count(Battery.id)).where(
                    Battery.station_id == st.id,
                    Battery.status == BatteryStatus.AVAILABLE,
                )
            ).one()
            rented_batt = db.exec(
                select(func.count(Battery.id)).where(
                    Battery.station_id == st.id,
                    Battery.status == BatteryStatus.RENTED,
                )
            ).one()
            active_rentals = db.exec(
                select(func.count(Rental.id)).where(
                    Rental.start_station_id == st.id,
                    Rental.status == RentalStatus.ACTIVE,
                )
            ).one()
            swaps = db.exec(
                select(func.count(SwapSession.id)).where(
                    SwapSession.station_id == st.id,
                )
            ).one()
            reviews = db.exec(
                select(func.count(Review.id)).where(Review.station_id == st.id)
            ).one()

            print(f"\n  📍 {st.name} (id={st.id})")
            print(f"     Batteries: {total_batt} total | {avail_batt} available | {rented_batt} rented")
            print(f"     Active Rentals: {active_rentals}")
            print(f"     Swaps: {swaps}")
            print(f"     Reviews: {reviews} | Rating: {st.rating}")

        print(f"\n  👥 Total Customers: {total_customers}")
        print("=" * 70)


if __name__ == "__main__":
    seed_dynamic()
