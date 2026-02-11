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
    def generate_settlement(dealer_id: int, start_date: datetime, end_date: datetime) -> Settlement:
        with Session(engine) as session:
            # Find unpaid commissions
            commissions = session.exec(select(CommissionLog).where(
                CommissionLog.dealer_id == dealer_id,
                CommissionLog.status == "pending",
                CommissionLog.created_at >= start_date,
                CommissionLog.created_at <= end_date
            )).all()
            
            total = sum(c.amount for c in commissions)
            deductions = total * 0.05 # Platform fee example
            net = total - deductions
            
            settlement = Settlement(
                dealer_id=dealer_id,
                start_date=start_date,
                end_date=end_date,
                total_commission=total,
                total_deductions=deductions,
                net_amount=net,
                status="pending",
                generated_at=datetime.utcnow()
            )
            session.add(settlement)
            session.commit()
            session.refresh(settlement)
            
            # Update Commissions
            for c in commissions:
                c.settlement_id = settlement.id
                c.status = "processing"
                session.add(c)
            session.commit()
            
            return settlement
