from sqlmodel import Session, select
from app.core.database import engine
from app.models.invoice import Invoice
from app.models.financial import Transaction
from app.models.commission import CommissionLog
from app.models.settlement import Settlement
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental
from app.models.swap import SwapSession
from datetime import datetime, UTC, timedelta
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

class FinancialService:
    
    @staticmethod
    def _get_next_invoice_number(session: Session) -> str:
        """Sequential invoice numbering: INV-YYYY-NNNN"""
        year = datetime.now(UTC).year
        prefix = f"INV-{year}-"
        
        # Find last invoice for this year
        last_invoice = session.exec(
            select(Invoice)
            .where(Invoice.invoice_number.like(f"{prefix}%"))
            .order_by(Invoice.invoice_number.desc())
        ).first()
        
        if not last_invoice:
            return f"{prefix}0001"
        
        try:
            last_num_str = last_invoice.invoice_number.split("-")[-1]
            next_num = int(last_num_str) + 1
            return f"{prefix}{next_num:04d}"
        except (ValueError, IndexError):
            return f"{prefix}{uuid.uuid4().hex[:4].upper()}"

    @staticmethod
    def create_invoice(transaction_id: int, user_id: int) -> Invoice:
        with Session(engine) as session:
            txn = session.get(Transaction, transaction_id)
            if not txn:
                raise ValueError("Transaction not found")
            
            # GST Calculation: 18% included in total
            total = txn.amount
            subtotal = round(total / 1.18, 2)
            tax = round(total - subtotal, 2)
            
            invoice = Invoice(
                user_id=user_id,
                transaction_id=transaction_id,
                invoice_number=FinancialService._get_next_invoice_number(session),
                amount=total,
                subtotal=subtotal,
                tax_amount=tax,
                total=total,
                gstin="27AAACW1234X1ZX",
                pdf_url=f"/api/v1/invoices/{transaction_id}/pdf", # Updated to local API
                created_at=datetime.now(UTC)
            )
            session.add(invoice)
            session.commit()
            session.refresh(invoice)
            return invoice

    @staticmethod
    def generate_settlement(db: Session, dealer_id: int, start_date: datetime, end_date: datetime) -> Settlement:
        """
        Gathers all pending commissions for a dealer in a date range and creates a settlement record.
        """
        # 1. Find unpaid commissions
        statement = select(CommissionLog).where(
            CommissionLog.dealer_id == dealer_id,
            CommissionLog.status == "pending",
            CommissionLog.created_at >= start_date,
            CommissionLog.created_at <= end_date
        )
        commissions = db.exec(statement).all()
        
        if not commissions:
            raise ValueError("No pending commissions found for this period")
            
        total_comm = sum(c.amount for c in commissions)
        deductions = total_comm * 0.02 # Example 2% platform TDS/Fee
        net_payable = total_comm - deductions
        
        settlement = Settlement(
            dealer_id=dealer_id,
            start_date=start_date,
            end_date=end_date,
            total_revenue=total_comm, # Total commission pool
            platform_fee=deductions,
            payable_amount=net_payable,
            status="generated",
            created_at=datetime.now(UTC)
        )
        db.add(settlement)
        db.commit()
        db.refresh(settlement)
        
        # 2. Update Commissions to link to this settlement
        for c in commissions:
            c.settlement_id = settlement.id
            c.status = "processing"
            db.add(c)
        db.commit()
        
        return settlement

    @staticmethod
    def process_payout(db: Session, settlement_id: int, payment_ref: str) -> Settlement:
        """
        Confirms bank transfer of the settlement amount.
        """
        settlement = db.get(Settlement, settlement_id)
        if not settlement:
            raise ValueError("Settlement record not found")
            
        settlement.status = "paid"
        settlement.paid_at = datetime.now(UTC)
        settlement.transaction_reference = payment_ref
        
        # Batch update commissions to 'paid'
        statement = select(CommissionLog).where(CommissionLog.settlement_id == settlement_id)
        commissions = db.exec(statement).all()
        for c in commissions:
            c.status = "paid"
            db.add(c)
            
        db.add(settlement)
        db.commit()
        db.refresh(settlement)
        return settlement

    @staticmethod
    def search_dealer_transactions(
        db: Session,
        dealer_id: int,
        query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        station_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[dict]:
        """
        Search and filter transactions for a dealer across all their stations.
        """
        from app.models.dealer import DealerProfile
        dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == dealer_id)).first()
        if not dealer:
            return []

        # Find all stations for this dealer
        station_q = select(Station.id).where(Station.dealer_id == dealer.id)
        if station_id:
            station_q = station_q.where(Station.id == station_id)
        station_ids = db.exec(station_q).all()
        if not station_ids:
            return []

        # We primarily search for Rentals starting at these stations 
        # or CommissionLogs for this dealer.
        # For simplicity in this implementation, we'll join Transactions with Rentals.
        stmt = (
            select(Transaction, Rental, User, Station)
            .join(Rental, Rental.id == Transaction.rental_id)
            .join(User, User.id == Transaction.user_id)
            .join(Station, Station.id == Rental.start_station_id)
            .where(Rental.start_station_id.in_(station_ids))
        )

        if start_date:
            stmt = stmt.where(Transaction.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Transaction.created_at <= end_date)
        if statuses:
            stmt = stmt.where(Transaction.status.in_(statuses))
        if types:
            stmt = stmt.where(Transaction.transaction_type.in_(types))
        if min_amount is not None:
            stmt = stmt.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            stmt = stmt.where(Transaction.amount <= max_amount)
        
        if query:
            # Search by TXN Ref, Customer Name, or Battery serial (via join)
            from app.models.battery import Battery
            stmt = stmt.join(Battery, Battery.id == Rental.battery_id).where(
                (Transaction.payment_gateway_ref.ilike(f"%{query}%")) |
                (User.full_name.ilike(f"%{query}%")) |
                (Battery.serial_number.ilike(f"%{query}%"))
            )

        stmt = stmt.offset(skip).limit(limit).order_by(Transaction.created_at.desc())
        results = db.exec(stmt).all()

        hydrated = []
        for txn, rental, user, station in results:
            # Calculate commission bit
            commission = db.exec(
                select(CommissionLog).where(CommissionLog.transaction_id == txn.id)
            ).first()
            
            # Duration in minutes
            duration = 0
            if rental.end_time:
                duration = int((rental.end_time - rental.start_time).total_seconds() / 60)
            elif rental.status == "active":
                duration = int((datetime.now(UTC) - rental.start_time).total_seconds() / 60)

            battery = db.get(Battery, rental.battery_id)
            
            hydrated.append({
                "id": txn.id,
                "user_id": user.id,
                "customer_name": user.full_name,
                "customer_phone": user.phone_number,
                "amount": float(txn.amount),
                "currency": txn.currency,
                "transaction_type": txn.transaction_type,
                "status": txn.status,
                "created_at": txn.created_at,
                "station_name": station.name,
                "battery_serial": battery.serial_number if battery else "N/A",
                "duration_minutes": duration,
                "net_amount": float(txn.amount - (commission.amount if commission else 0)),
                "commission_amount": float(commission.amount if commission else 0),
                "settlement_status": commission.status if commission else "N/A",
                "payment_method": txn.payment_method,
                "payment_gateway_ref": txn.payment_gateway_ref
            })

        return hydrated

    @staticmethod
    def get_transaction_lifecycle(db: Session, txn_id: int) -> List[dict]:
        """
        Returns the lifecycle timeline of a transaction.
        """
        txn = db.get(Transaction, txn_id)
        if not txn:
            return []

        rental = None
        if txn.rental_id:
            rental = db.get(Rental, txn.rental_id)

        events = []
        
        # 1. Rental Started
        if rental:
            events.append({
                "event_type": "Rental Started",
                "timestamp": rental.start_time,
                "is_completed": True
            })

        # 2. Payment Captured
        events.append({
            "event_type": "Payment Captured",
            "timestamp": txn.created_at,
            "is_completed": txn.status == "success"
        })

        # 3. Commission Calculated
        commission = db.exec(
            select(CommissionLog).where(CommissionLog.transaction_id == txn_id)
        ).first()
        if commission:
            events.append({
                "event_type": "Commission Calculated",
                "timestamp": commission.created_at,
                "is_completed": True
            })
        else:
            events.append({
                "event_type": "Commission Calculated",
                "timestamp": txn.created_at + timedelta(minutes=5),
                "is_completed": False
            })

        # 4. Settlement Queued / Completed
        if commission and commission.settlement_id:
            settlement = db.get(Settlement, commission.settlement_id)
            events.append({
                "event_type": f"Settlement {settlement.status.capitalize()}",
                "timestamp": settlement.created_at,
                "is_completed": settlement.status == "paid"
            })
        else:
            events.append({
                "event_type": "Settlement Pending",
                "timestamp": datetime.now(UTC) + timedelta(days=30),
                "is_completed": False
            })

        return events

