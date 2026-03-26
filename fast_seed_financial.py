import os
import sys
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from sqlmodel import Session, select
from app.models.user import User, UserType, UserStatus, KYCStatus
from app.models.station import Station
from app.models.battery import Battery
from app.models.dealer import DealerProfile
from app.models.commission import CommissionConfig
from app.models.revenue_report import RevenueReport
from app.models.settlement import Settlement
from app.models.swap import SwapSession
from app.models.financial import Transaction, TransactionType, TransactionStatus, Wallet
from app.models.invoice import Invoice

from app.core.security import get_password_hash
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def fast_seed():
    from sqlmodel import SQLModel
    print("Ensuring schema is up-to-date...")
    SQLModel.metadata.create_all(engine)
    print("Starting FAST financial seeding via SQLModel...")
    with Session(engine) as session:
        # 1. Create a Dealer and an Admin
        print("Seeding Users...")
        # Upsert admin
        admin = session.exec(select(User).where(User.email == 'admin@wezu.energy')).first()
        if not admin:
            admin = User(
                email='admin@wezu.energy', full_name='Super Admin',
                user_type=UserType.ADMIN, status=UserStatus.ACTIVE,
                is_superuser=True
            )
        admin.hashed_password = get_password_hash("Admin@123")
        session.add(admin)

        # Upsert dealer
        dealer_user = session.exec(select(User).where(User.email == 'dealer@wezu.energy')).first()
        if not dealer_user:
            dealer_user = User(
                email='dealer@wezu.energy', full_name='Test Dealer',
                user_type=UserType.DEALER, status=UserStatus.ACTIVE
            )
        dealer_user.hashed_password = get_password_hash("Admin@123")
        session.add(dealer_user)

        # Upsert customer
        customer = session.exec(select(User).where(User.email == 'customer@wezu.energy')).first()
        if not customer:
            customer = User(
                email='customer@wezu.energy', full_name='Test Customer',
                user_type=UserType.CUSTOMER, status=UserStatus.ACTIVE
            )
        customer.hashed_password = get_password_hash("Admin@123")
        session.add(customer)
        session.commit()
        
        # 2. Add Dealer Profile
        print("Seeding Dealer Profile...")
        dealer_profile = DealerProfile(
            user_id=dealer_user.id, business_name='Test Dealer Business',
            contact_person='Test Contact', contact_email='dealer@wezu.energy',
            contact_phone='+919876543210', address_line1='Plot 123, HITEC City',
            city='Hyderabad', state='Telangana', pincode='500081', is_active=True
        )
        session.add(dealer_profile)
        session.commit()
        
        # 3. Add Commission Config
        print("Seeding Commission Config...")
        config = CommissionConfig(
            dealer_id=dealer_user.id, transaction_type='rental', 
            percentage=10.0, is_active=True
        )
        session.add(config)
        
        # 4. Add Station
        print("Seeding Station...")
        station = Station(
            name='Central Station', address='123 Tech Park', city='Hyderabad',
            latitude=17.44, longitude=78.38, dealer_id=dealer_profile.id,
            status='operational', total_slots=10, available_batteries=5
        )
        session.add(station)
        session.commit()
        
        # 5. Add Battery
        print("Seeding Battery...")
        battery = Battery(
            serial_number='BAT-FAST-001', station_id=station.id,
            status='available', health_status='GOOD', purchase_cost=45000.0,
            battery_type='48V/30Ah'
        )
        session.add(battery)
        session.commit()
        
        # 6. Add Swap Sessions (for Profitability Analysis)
        print("Seeding Swap Sessions...")
        for i in range(10):
            swap = SwapSession(
                user_id=customer.id, station_id=station.id,
                new_battery_id=battery.id, swap_amount=200.0,
                status="completed", created_at=datetime.utcnow() - timedelta(days=i)
            )
            session.add(swap)
        session.commit()
        
        # 7. Add Revenue Reports
        print("Seeding Revenue Reports...")
        for i in range(1, 4):
            report_date = (date.today() - timedelta(days=30*i))
            report = RevenueReport(
                report_type='monthly', 
                period_start=report_date.replace(day=1),
                period_end=report_date, 
                total_revenue=10000.0 * i,
                total_transactions=100, 
                breakdown_by_source={"rental": 8000.0, "purchase": 2000.0}
            )
            session.add(report)
            
        # 8. Add Transactions and Invoices
        print("Seeding Transactions and Invoices...")
        wallet = Wallet(user_id=customer.id, balance=1000.0)
        session.add(wallet)
        session.commit()

        for i in range(5):
            amount = 500.0
            subtotal = round(amount / 1.18, 2)
            tax = round(amount - subtotal, 2)
            
            tx = Transaction(
                user_id=customer.id, wallet_id=wallet.id, amount=amount,
                subtotal=subtotal, tax_amount=tax,
                transaction_type=TransactionType.WALLET_TOPUP,
                status=TransactionStatus.SUCCESS,
                description=f"Seeded Topup #{i+1}",
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            session.add(tx)
            session.commit()
            
            # Add Invoice
            inv = Invoice(
                user_id=customer.id, transaction_id=tx.id,
                invoice_number=f"INV-2026-000{i+1}",
                amount=amount, subtotal=subtotal, tax_amount=tax, total=amount,
                gstin="27AAACW1234X1ZX",
                created_at=tx.created_at
            )
            session.add(inv)

        # 9. Add Settlements (1 Paid, 1 Failed)
        print("Seeding Settlements...")
        s1 = Settlement(
            dealer_id=dealer_user.id, 
            settlement_month="2026-02",
            start_date=datetime(2026, 2, 1),
            end_date=datetime(2026, 2, 28),
            total_revenue=15000.0,
            total_commission=1500.0,
            tax_amount=270.0, # 18% of commission
            net_payable=1230.0,
            status='paid',
            paid_at=datetime.utcnow(),
            transaction_reference="PAY-TEST-SUCCESS-001"
        )
        session.add(s1)

        s2 = Settlement(
            dealer_id=dealer_user.id,
            settlement_month="2026-03",
            start_date=datetime(2026, 3, 1),
            end_date=datetime(2026, 3, 25),
            total_revenue=8000.0,
            total_commission=800.0,
            tax_amount=144.0,
            net_payable=656.0,
            status='failed',
            failure_reason="Insufficient balance in platform payout wallet",
            due_date=datetime.utcnow() + timedelta(days=5)
        )
        session.add(s2)
        session.commit()

    print("FAST seeding completed successfully!")

if __name__ == "__main__":
    fast_seed()
