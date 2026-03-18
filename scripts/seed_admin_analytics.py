import logging
import random
import sys
import os
from datetime import datetime, timedelta, date
from sqlmodel import Session, select

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import engine
from app.models.user import User, UserType, UserStatus
from app.models.station import Station, StationStatus
from app.models.battery import Battery, BatteryStatus, BatteryHealth
from app.models.battery_health import BatteryHealthSnapshot
from app.models.rental import Rental, RentalStatus
from app.models.financial import Transaction, TransactionType, TransactionStatus, Wallet
from app.models.support import SupportTicket, TicketStatus, TicketPriority
from app.models.kyc import KYCRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_admin_analytics():
    with Session(engine) as session:
        logger.info("👨‍💼 Seeding Admin Analytics Data...")
        
        # Fetch existing base data
        all_users = session.exec(select(User)).all()
        users = [u for u in all_users if u.user_type == "customer" or (hasattr(u.user_type, "value") and u.user_type.value == "customer")]
        stations = session.exec(select(Station)).all()
        batteries = session.exec(select(Battery)).all()
        admin_user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()


        if not users or not stations or not batteries or not admin_user:
            logger.error("❌ Missing base data. Run seed_full_db.py first.")
            return

        now = datetime.utcnow()

        # Normalize station metadata for analytics visuals
        for station in stations:
            if not station.rating or station.rating == 0:
                station.rating = round(random.uniform(4.0, 4.9), 1)
            if not station.available_batteries:
                station.available_batteries = random.randint(4, max(5, station.total_slots))
            station.available_slots = max(station.total_slots - station.available_batteries, 0)
            session.add(station)
        session.commit()

        # 1. Seed User Growth (Backdated users)
        logger.info("👥 Seeding User Growth data...")
        cities = ["Hyderabad", "Bangalore", "Chennai", "Pune", "Mumbai"]
        for i in range(50):
            days_ago = random.randint(1, 120)
            created_at = now - timedelta(days=days_ago)
            new_user = User(
                phone_number=f"7000000{i:03}",
                email=f"user_{i}@example.com",
                full_name=f"Analytics User {i}",
                user_type=UserType.CUSTOMER,
                status=UserStatus.ACTIVE,
                created_at=created_at
            )
            session.add(new_user)
            session.flush()

            # Seed KYC (for conversion funnel)
            if random.random() > 0.2: # 80% have KYC
                kyc_status = "verified" if random.random() > 0.3 else "pending"
                kyc = KYCRecord(
                    user_id=new_user.id,
                    status=kyc_status,
                    submitted_at=created_at + timedelta(hours=random.randint(1, 24)),
                    verified_at=created_at + timedelta(days=1) if kyc_status == "verified" else None,
                    verified_by=admin_user.id if kyc_status == "verified" else None
                )
                session.add(kyc)
            
            # Seed Wallet
            wallet = Wallet(user_id=new_user.id, balance=random.uniform(100, 1000))
            session.add(wallet)

        session.commit()
        # Refresh users list to include new ones
        users = session.exec(select(User).where(User.user_type == UserType.CUSTOMER)).all()

        # 2. Seed Revenue & Trends (Rentals & Transactions)
        logger.info("💰 Seeding Revenue & Trends...")
        for _ in range(320):
            user = random.choice(users)
            station_start = random.choice(stations)
            battery = random.choice(batteries)
            
            days_ago = random.randint(0, 90)
            start_time = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            duration_hours = random.randint(2, 48)
            end_time = start_time + timedelta(hours=duration_hours)
            
            amount = duration_hours * 10 # 10 INR per hour
            
            rental = Rental(
                user_id=user.id,
                battery_id=battery.id,
                start_station_id=station_start.id,
                end_station_id=random.choice(stations).id if random.random() > 0.1 else None,
                start_time=start_time,
                expected_end_time=start_time + timedelta(days=1),
                end_time=end_time if random.random() > 0.1 else None,
                total_amount=amount,
                status=RentalStatus.COMPLETED if random.random() > 0.1 else RentalStatus.ACTIVE,
                created_at=start_time
            )
            session.add(rental)
            session.flush()

            # Create Transaction for rental
            transaction = Transaction(
                user_id=user.id,
                rental_id=rental.id,
                amount=amount,
                transaction_type=TransactionType.RENTAL_PAYMENT,
                status=TransactionStatus.SUCCESS,
                created_at=end_time if rental.end_time else start_time
            )
            session.add(transaction)

        # 3. Seed Support Metrics
        logger.info("🛠️ Seeding Support Metrics...")
        categories = ["billing", "technical", "hardware", "other"]
        for _ in range(40):
            user = random.choice(users)
            days_ago = random.randint(0, 60)
            created_at = now - timedelta(days=days_ago)
            
            status = random.choice(list(TicketStatus))
            ticket = SupportTicket(
                user_id=user.id,
                subject=f"Issue with {random.choice(['billing', 'battery', 'station'])}",
                description="Randomly generated support issue for analytics.",
                status=status,
                priority=random.choice(list(TicketPriority)),
                category=random.choice(categories),
                created_at=created_at,
                resolved_at=created_at + timedelta(days=random.randint(1, 5)) if status == TicketStatus.RESOLVED else None
            )
            session.add(ticket)

        # 4. Diversify Station Performance (City distribution)
        logger.info("🏢 Updating Station distributions...")
        for station in stations:
            station.city = random.choice(cities)
            session.add(station)

        # 5. Diversify Battery Health Distribution
        logger.info("🔋 Diversifying Battery Health...")
        for battery in batteries:
            battery.health_percentage = random.uniform(65.0, 100.0)
            if battery.health_percentage < 70:
                battery.health_status = BatteryHealth.CRITICAL
            elif battery.health_percentage < 80:
                battery.health_status = BatteryHealth.FAIR
            else:
                battery.health_status = BatteryHealth.GOOD
            session.add(battery)

        logger.info("🩺 Capturing battery health snapshots for trend baselines...")
        for battery in batteries[:40]:
            base_health = battery.health_percentage
            for days_back in range(0, 60, 10):
                drift = random.uniform(-5.0, 2.0)
                session.add(
                    BatteryHealthSnapshot(
                        battery_id=battery.id,
                        health_percentage=max(50.0, min(100.0, base_health + drift)),
                        recorded_at=now - timedelta(days=days_back),
                    )
                )

        session.commit()
        logger.info("✅ Admin Analytics Seeding Complete!")

if __name__ == "__main__":
    seed_admin_analytics()
