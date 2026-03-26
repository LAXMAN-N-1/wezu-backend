from sqlmodel import Session, select
from app.core.database import engine
from app.models.invoice import Invoice
from app.models.financial import Transaction
from app.models.commission import CommissionLog
from app.models.settlement import Settlement
from datetime import datetime, timedelta
import uuid

class FinancialService:
    
    @staticmethod
    def _get_next_invoice_number(session: Session) -> str:
        """Sequential invoice numbering: INV-YYYY-NNNN"""
        year = datetime.utcnow().year
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
                created_at=datetime.utcnow()
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
            created_at=datetime.utcnow()
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
        settlement.paid_at = datetime.utcnow()
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

