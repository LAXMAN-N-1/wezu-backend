from __future__ import annotations
"""
Final ultra-robust seed script: Seeds for all dealers using raw SQL and uppercase Enums.
"""
import sys
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from sqlmodel import Session, select
from app.db.session import engine
from app.models.dealer import DealerProfile

SUBJECTS = [
    "Battery not charging @ station", "Refund request - failed swap", 
    "Station offline City Center", "App sync error", "Swap module unresponsive"
]

def seed():
    with Session(engine) as db:
        dealers = db.exec(select(DealerProfile)).all()
        if not dealers:
            print("No dealers found.")
            return

        for d in dealers:
            print(f"\nDealer: {d.business_name} (u_id={d.user_id})")
            
            # --- Tickets ---
            res = db.execute(text("SELECT count(*) FROM support_tickets WHERE user_id = :u"), {"u": d.user_id}).scalar()
            if res < 5:
                for subj in SUBJECTS:
                    db.execute(text("""
                        INSERT INTO support_tickets (user_id, subject, description, category, priority, status, created_at, updated_at)
                        VALUES (:u, :s, :desc, 'Hardware', :p, :st, now(), now())
                    """), {
                        "u": d.user_id, "s": subj, "desc": f"Issue details for {subj}",
                        "p": random.choice(["LOW", "MEDIUM", "HIGH"]), "st": "OPEN"
                    })
                db.commit()
                print("  ✓ Tickets seeded.")

            # --- Wallet ---
            has_wallet = db.execute(text("SELECT count(*) FROM wallets WHERE user_id = :u"), {"u": d.user_id}).scalar()
            if not has_wallet:
                db.execute(text("""
                    INSERT INTO wallets (user_id, balance, currency, is_frozen, updated_at, cashback_balance)
                    VALUES (:u, 15000.0, 'INR', false, now(), 250.0)
                """), {"u": d.user_id})
                db.commit()
                print("  ✓ Wallet created.")

            # --- Transactions ---
            res_tx = db.execute(text("SELECT count(*) FROM transactions WHERE user_id = :u"), {"u": d.user_id}).scalar()
            if res_tx < 5:
                w_id = db.execute(text("SELECT id FROM wallets WHERE user_id = :u"), {"u": d.user_id}).scalar()
                for i in range(10):
                    db.execute(text("""
                        INSERT INTO transactions (user_id, wallet_id, amount, currency, transaction_type, status, payment_method, description, created_at, updated_at)
                        VALUES (:u, :w_id, :a, 'INR', :tt, 'SUCCESS', 'upi', :desc, now(), now())
                    """), {
                        "u": d.user_id, "w_id": w_id, "a": float(random.randint(50, 500)),
                        "tt": random.choice(["RENTAL_PAYMENT", "WALLET_TOPUP", "SWAP_FEE"]),
                        "desc": f"Seeded TXN {i}"
                    })
                db.commit()
                print("  ✓ Transactions seeded.")

            # --- Inventory ---
            res_inv = db.execute(text("SELECT count(*) FROM dealer_inventories WHERE dealer_id = :d"), {"d": d.id}).scalar()
            if res_inv < 2:
                for mod in ["WZ-LFP-X1", "WZ-LFP-X2"]:
                    db.execute(text("""
                        INSERT INTO dealer_inventories (dealer_id, battery_model, quantity_available, quantity_reserved, quantity_damaged, reorder_level, max_capacity, created_at, updated_at)
                        VALUES (:d, :m, :q, 0, 0, 5, 50, now(), now())
                    """), {"d": d.id, "m": mod, "q": random.randint(10, 40)})
                db.commit()
                print("  ✓ Inventory seeded.")

            # --- Promotions ---
            res_p = db.execute(text("SELECT count(*) FROM dealer_promotions WHERE dealer_id = :d"), {"d": d.id}).scalar()
            if res_p < 2:
                for i in range(2):
                    db.execute(text("""
                        INSERT INTO dealer_promotions (
                            dealer_id, name, promo_code, discount_type, discount_value, 
                            start_date, end_date, is_active, created_at, requires_approval, 
                            usage_limit_per_user, usage_count, applicable_to
                        )
                        VALUES (:d, :n, :c, 'PERCENTAGE', 10.0, now(), now() + interval '30 days', true, now(), true, 1, 0, 'ALL')
                    """), {"d": d.id, "n": f"Welcome {i}", "c": f"WELCOME{d.id}_{i}"})
                db.commit()
                print("  ✓ Promotions seeded.")

            # --- Documents ---
            res_doc = db.execute(text("SELECT count(*) FROM dealer_documents WHERE dealer_id = :d"), {"d": d.id}).scalar()
            if res_doc < 2:
                for dt in ["GST_CERT", "ID_PROOF"]:
                    db.execute(text("""
                        INSERT INTO dealer_documents (dealer_id, document_type, file_url, uploaded_at, is_verified)
                        VALUES (:d, :dt, 'https://wezu.storage/fake.pdf', now(), false)
                    """), {"d": d.id, "dt": dt})
                db.commit()
                print("  ✓ Documents seeded.")

        print("\n✅ Seed complete (Final Raw SQL)!")

if __name__ == "__main__":
    seed()
