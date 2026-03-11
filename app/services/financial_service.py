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
    def create_invoice(transaction_id: int, user_id: int) -> Invoice:
        with Session(engine) as session:
            txn = session.get(Transaction, transaction_id)
            if not txn:
                raise ValueError("Transaction not found")
            
            # Simple Logic: Invoice Amount = Txn Amount
            # Tax = 18% GST included
            amount = txn.amount
            tax = amount * 0.18 # simple assumption
            
            invoice = Invoice(
                user_id=user_id,
                transaction_id=transaction_id,
                invoice_number=f"INV-{datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}",
                amount=amount,
                tax_amount=tax,
                gstin="GSTINSC123456",
                pdf_url=f"https://s3.wezu.com/invoices/INV-{txn.id}.pdf", # Mock
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

