"""
Populate transactions + support tickets using raw SQL to bypass enum case issues.
The ORM sends Python enum names (uppercase) but the DB expects lowercase values.
"""
import random
from datetime import datetime, timedelta
from sqlalchemy import text
from app.core.database import engine
from sqlmodel import Session, select
from app.models.rental import Rental, RentalStatus
from app.models.user import User, UserType

random.seed(99)

def main():
    with Session(engine) as db:
        # Get existing entities
        customers = db.exec(select(User).where(User.user_type == UserType.CUSTOMER)).all()
        customer_ids = [c.id for c in customers]
        now = datetime.utcnow()

        # Get all completed rentals
        completed_rentals = db.exec(
            select(Rental).where(Rental.status == RentalStatus.COMPLETED)
        ).all()
        print(f"Found {len(completed_rentals)} completed rentals, {len(customer_ids)} customers")

        # =========================================================
        # 1. Create rental payment transactions (raw SQL)
        # =========================================================
        print("\n--- Creating rental payment transactions ---")
        payment_methods = ["upi", "card", "wallet", "net_banking"]
        tx_count = 0

        for rental in completed_rentals:
            if rental.total_amount and rental.total_amount > 0:
                tx_time = rental.end_time or rental.created_at
                pm = random.choice(payment_methods)
                ref = f"PAY-{random.randint(100000, 999999)}"
                db.exec(text("""
                    INSERT INTO transactions (user_id, rental_id, amount, currency, transaction_type, status, payment_method, payment_gateway_ref, description, created_at, updated_at)
                    VALUES (:user_id, :rental_id, :amount, 'INR', 'rental_payment', 'success', :pm, :ref, :desc, :created, :updated)
                """), params={
                    "user_id": rental.user_id,
                    "rental_id": rental.id,
                    "amount": rental.total_amount,
                    "pm": pm,
                    "ref": ref,
                    "desc": f"Rental payment for rental #{rental.id}",
                    "created": tx_time,
                    "updated": tx_time,
                })
                tx_count += 1

        # Wallet topups
        for i in range(25):
            days_ago = random.randint(1, 60)
            tx_time = now - timedelta(days=days_ago, hours=random.uniform(0, 24))
            amount = round(random.uniform(100, 2000), 2)
            pm = random.choice(payment_methods)
            ref = f"TOP-{random.randint(100000, 999999)}"
            db.exec(text("""
                INSERT INTO transactions (user_id, amount, currency, transaction_type, status, payment_method, payment_gateway_ref, description, created_at, updated_at)
                VALUES (:user_id, :amount, 'INR', 'wallet_topup', 'success', :pm, :ref, 'Wallet top-up', :created, :updated)
            """), params={
                "user_id": random.choice(customer_ids),
                "amount": amount,
                "pm": pm,
                "ref": ref,
                "created": tx_time,
                "updated": tx_time,
            })
            tx_count += 1

        # Purchase transactions
        for i in range(10):
            days_ago = random.randint(1, 45)
            tx_time = now - timedelta(days=days_ago, hours=random.uniform(0, 24))
            amount = round(random.uniform(500, 3000), 2)
            pm = random.choice(payment_methods)
            ref = f"PUR-{random.randint(100000, 999999)}"
            db.exec(text("""
                INSERT INTO transactions (user_id, amount, currency, transaction_type, status, payment_method, payment_gateway_ref, description, created_at, updated_at)
                VALUES (:user_id, :amount, 'INR', 'purchase', 'success', :pm, :ref, 'Battery purchase', :created, :updated)
            """), params={
                "user_id": random.choice(customer_ids),
                "amount": amount,
                "pm": pm,
                "ref": ref,
                "created": tx_time,
                "updated": tx_time,
            })
            tx_count += 1

        db.commit()
        print(f"  Created {tx_count} transactions")

        # =========================================================
        # 2. Support tickets (raw SQL)
        # =========================================================
        print("\n--- Creating support tickets ---")
        tickets = [
            ("Battery not charging", "Battery WZ-1234 stuck at 20%", "battery", "high", "open"),
            ("Swap station offline", "Station Indiranagar 2 not responding", "station", "critical", "open"),
            ("Refund request", "Overcharged on rental #45", "billing", "medium", "in_progress"),
            ("App login issue", "Cannot login with phone number", "account", "low", "resolved"),
            ("Payment failed", "UPI payment deducted but not credited", "billing", "high", "open"),
            ("Damaged battery", "Battery casing cracked at station 3", "battery", "high", "in_progress"),
            ("Feature request", "Add battery booking feature", "feature", "low", "resolved"),
            ("Slow charging", "Charging speed decreased at station 5", "station", "medium", "open"),
        ]

        for subject, desc, category, priority, status in tickets:
            days_ago = random.randint(0, 30)
            created = now - timedelta(days=days_ago, hours=random.uniform(0, 24))
            updated = created + timedelta(hours=random.uniform(1, 48))
            resolved = (created + timedelta(hours=random.uniform(2, 72))) if status == "resolved" else None
            db.exec(text("""
                INSERT INTO support_tickets (user_id, subject, description, status, priority, category, created_at, updated_at, resolved_at)
                VALUES (:user_id, :subject, :desc, :status, :priority, :category, :created, :updated, :resolved)
            """), params={
                "user_id": random.choice(customer_ids),
                "subject": subject,
                "desc": desc,
                "status": status,
                "priority": priority,
                "category": category,
                "created": created,
                "updated": updated,
                "resolved": resolved,
            })
        db.commit()
        print(f"  Created {len(tickets)} support tickets")

        # =========================================================
        # Summary
        # =========================================================
        from sqlmodel import func 
        from app.models.financial import Transaction, TransactionStatus
        from app.models.battery_health import BatteryHealthSnapshot
        from app.models.support import SupportTicket

        total_tx = db.exec(select(func.count(Transaction.id))).one()
        total_rentals = db.exec(select(func.count(Rental.id))).one()
        total_snaps = db.exec(select(func.count(BatteryHealthSnapshot.id))).one()
        total_tickets = db.exec(select(func.count(SupportTicket.id))).one()

        # Revenue via raw SQL to avoid enum issue
        rev_result = db.exec(text("SELECT SUM(amount) FROM transactions WHERE status = 'success'"))
        total_revenue = rev_result.one()[0] or 0

        print(f"\n=== Final DB State ===")
        print(f"  Transactions: {total_tx}")
        print(f"  Rentals: {total_rentals}")
        print(f"  Health Snapshots: {total_snaps}")
        print(f"  Support Tickets: {total_tickets}")
        print(f"  Total Revenue: ₹{total_revenue:,.2f}")
        print("\nDone! Restart the backend server to pick up changes.")


if __name__ == "__main__":
    main()
