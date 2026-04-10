from sqlmodel import Session, select
from datetime import datetime, UTC, timedelta
from typing import Optional, List
from app.models.settlement import Settlement
from app.models.commission import CommissionLog
from app.models.chargeback import Chargeback
from app.models.swap import SwapSession
from app.models.station import Station
from app.models.dealer import DealerProfile
from app.services.commission_service import CommissionService
import logging
import uuid

logger = logging.getLogger("wezu_settlements")


class SettlementService:

    @staticmethod
    def generate_monthly_settlement(
        db: Session, dealer_id: int, month: str
    ) -> Settlement:
        """
        Generate settlement for a dealer for a given month (format: 'YYYY-MM').
        Aggregates commissions, deducts chargebacks, rounds to 2dp.
        """
        year, mon = map(int, month.split("-"))
        start_date = datetime(year, mon, 1)
        if mon == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, mon + 1, 1) - timedelta(seconds=1)

        # Check if settlement already exists for this period
        existing = db.exec(
            select(Settlement).where(
                Settlement.dealer_id == dealer_id,
                Settlement.settlement_month == month,
            )
        ).first()
        if existing:
            return existing

        # 1. Sum pending commissions for the period
        commissions = db.exec(
            select(CommissionLog).where(
                CommissionLog.dealer_id == dealer_id,
                CommissionLog.status == "pending",
                CommissionLog.created_at >= start_date,
                CommissionLog.created_at <= end_date,
            )
        ).all()
        total_commission = round(sum(c.amount for c in commissions), 2)

        # 2. Aggregate swap revenue at dealer stations
        dealer_profile = db.exec(
            select(DealerProfile).where(DealerProfile.user_id == dealer_id)
        ).first()

        total_revenue = 0.0
        if dealer_profile:
            station_ids = db.exec(
                select(Station.id).where(Station.dealer_id == dealer_profile.id)
            ).all()
            if station_ids:
                swaps = db.exec(
                    select(SwapSession).where(
                        SwapSession.station_id.in_(station_ids),
                        SwapSession.status == "completed",
                        SwapSession.payment_status == "paid",
                        SwapSession.completed_at >= start_date,
                        SwapSession.completed_at <= end_date,
                    )
                ).all()
                total_revenue = round(sum(s.amount for s in swaps), 2)

        # 3. Deduct chargebacks
        chargebacks = db.exec(
            select(Chargeback).where(
                Chargeback.dealer_id == dealer_id,
                Chargeback.status == "pending",
                Chargeback.created_at >= start_date,
                Chargeback.created_at <= end_date,
            )
        ).all()
        chargeback_amount = round(sum(cb.amount for cb in chargebacks), 2)

        # 4. Calculate net payable
        # GST (18%) on commission
        tax_amount = round(total_commission * 0.18, 2)
        net_payable = round(total_commission - chargeback_amount, 2)
        if net_payable < 0:
            net_payable = 0.0

        # 5. Create settlement record
        due_date = (end_date + timedelta(days=1)).replace(day=10, hour=0, minute=0, second=0)
        
        settlement = Settlement(
            dealer_id=dealer_id,
            settlement_month=month,
            start_date=start_date,
            end_date=end_date,
            due_date=due_date,
            total_revenue=total_revenue,
            total_commission=total_commission,
            chargeback_amount=chargeback_amount,
            tax_amount=tax_amount,
            net_payable=net_payable,
            status="generated",
        )
        db.add(settlement)
        db.commit()
        db.refresh(settlement)

        # Link commissions to this settlement
        for c in commissions:
            c.settlement_id = settlement.id
            c.status = "processing"
            db.add(c)

        # Mark chargebacks as deducted
        for cb in chargebacks:
            cb.settlement_id = settlement.id
            cb.status = "deducted"
            db.add(cb)

        db.commit()

        logger.info(
            f"Settlement generated for dealer {dealer_id}, month {month}: "
            f"commission={total_commission}, chargebacks={chargeback_amount}, "
            f"net={net_payable}"
        )
        return settlement

    @staticmethod
    def process_batch_payments(db: Session, month: str) -> dict:
        """
        Batch process all 'generated' settlements for a month.
        Simulates payment gateway call and generates proof receipts.
        """
        settlements = db.exec(
            select(Settlement).where(
                Settlement.settlement_month == month,
                Settlement.status == "generated",
            )
        ).all()

        processed = 0
        failed = 0

        for settlement in settlements:
            try:
                # Mock payment gateway call
                txn_ref = f"PAY-{month}-{uuid.uuid4().hex[:8].upper()}"
                proof_url = f"https://s3.wezu.com/settlements/{settlement.id}/receipt.pdf"

                settlement.status = "paid"
                settlement.transaction_reference = txn_ref
                settlement.payment_proof_url = proof_url
                settlement.paid_at = datetime.now(UTC)
                db.add(settlement)

                # Mark linked commissions as paid
                linked_commissions = db.exec(
                    select(CommissionLog).where(
                        CommissionLog.settlement_id == settlement.id
                    )
                ).all()
                for cl in linked_commissions:
                    cl.status = "paid"
                    db.add(cl)

                processed += 1
            except Exception as e:
                settlement.status = "failed"
                settlement.failure_reason = str(e)
                db.add(settlement)
                failed += 1
                logger.error(f"Payment failed for settlement {settlement.id}: {e}")

        db.commit()

        return {
            "month": month,
            "total": len(settlements),
            "processed": processed,
            "failed": failed,
        }

    @staticmethod
    def process_single_payment(db: Session, settlement_id: int) -> Settlement:
        """Process a single settlement payment (used for retries)."""
        settlement = db.get(Settlement, settlement_id)
        if not settlement:
            raise ValueError("Settlement not found")
        
        # Only allow retrying if failed or generated
        if settlement.status not in ("failed", "generated"):
            raise ValueError(f"Cannot process settlement with status {settlement.status}")
        
        try:
            # Mock payment gateway call
            txn_ref = f"PAY-RETRY-{uuid.uuid4().hex[:8].upper()}"
            proof_url = f"https://s3.wezu.com/settlements/{settlement.id}/receipt.pdf"

            settlement.status = "paid"
            settlement.transaction_reference = txn_ref
            settlement.payment_proof_url = proof_url
            settlement.paid_at = datetime.now(UTC)
            settlement.failure_reason = None # Clear failure reason on success
            db.add(settlement)

            # Mark linked commissions as paid
            linked_commissions = db.exec(
                select(CommissionLog).where(
                    CommissionLog.settlement_id == settlement.id
                )
            ).all()
            for cl in linked_commissions:
                cl.status = "paid"
                db.add(cl)
            
            db.commit()
            db.refresh(settlement)
            return settlement
        except Exception as e:
            settlement.status = "failed"
            settlement.failure_reason = str(e)
            db.add(settlement)
            db.commit()
            logger.error(f"Payment retry failed for settlement {settlement.id}: {e}")
            raise ValueError(f"Payment processing failed: {e}")

    @staticmethod
    def get_dealer_dashboard(db: Session, dealer_id: int) -> dict:
        """
        Returns dealer's commission dashboard:
        - current_month_earnings
        - last_12_months history
        - pending_settlements count & amount
        - paid_settlements count & amount
        """
        now = datetime.now(UTC)
        current_month = now.strftime("%Y-%m")

        # Current month pending commissions (not yet settled)
        current_commissions = db.exec(
            select(CommissionLog).where(
                CommissionLog.dealer_id == dealer_id,
                CommissionLog.status == "pending",
                CommissionLog.created_at >= datetime(now.year, now.month, 1),
            )
        ).all()
        current_month_earnings = round(sum(c.amount for c in current_commissions), 2)

        # Last 12 months settlements
        twelve_months_ago = now - timedelta(days=365)
        settlements = db.exec(
            select(Settlement).where(
                Settlement.dealer_id == dealer_id,
                Settlement.start_date >= twelve_months_ago,
            ).order_by(Settlement.settlement_month.desc())
        ).all()

        history = [
            {
                "month": s.settlement_month,
                "total_commission": s.total_commission,
                "chargebacks": s.chargeback_amount,
                "net_payable": s.net_payable,
                "status": s.status,
                "paid_at": s.paid_at.isoformat() if s.paid_at else None,
            }
            for s in settlements
        ]

        pending = [s for s in settlements if s.status in ("pending", "generated")]
        paid = [s for s in settlements if s.status == "paid"]

        # Calculate total platform fees deducted across history
        total_platform_fees = round(sum(s.total_commission * 0.02 for s in settlements), 2)

        return {
            "current_month": current_month,
            "current_month_earnings": current_month_earnings,
            "total_platform_fees": total_platform_fees,
            "history": history,
            "pending_settlements": {
                "count": len(pending),
                "total_amount": round(sum(s.net_payable for s in pending), 2),
            },
            "paid_settlements": {
                "count": len(paid),
                "total_amount": round(sum(s.net_payable for s in paid), 2),
            },
            "next_payout": {
                "amount": round(sum(s.net_payable for s in pending), 2),
                "date": (now.replace(day=28) + timedelta(days=5)).replace(day=10).isoformat(),
            }
        }

    @staticmethod
    def get_transaction_detail(db: Session, settlement_id: int) -> dict:
        """
        Returns swap-level line items for a settlement.
        """
        settlement = db.get(Settlement, settlement_id)
        if not settlement:
            return None

        commissions = db.exec(
            select(CommissionLog).where(
                CommissionLog.settlement_id == settlement_id
            )
        ).all()

        chargebacks = db.exec(
            select(Chargeback).where(Chargeback.settlement_id == settlement_id)
        ).all()

        return {
            "settlement_id": settlement.id,
            "month": settlement.settlement_month,
            "commission_items": [
                {
                    "id": c.id,
                    "transaction_id": c.transaction_id,
                    "amount": c.amount,
                    "status": c.status,
                    "created_at": c.created_at.isoformat(),
                }
                for c in commissions
            ],
            "chargeback_items": [
                {
                    "id": cb.id,
                    "swap_session_id": cb.swap_session_id,
                    "amount": cb.amount,
                    "reason": cb.reason,
                    "status": cb.status,
                }
                for cb in chargebacks
            ],
            "summary": {
                "total_commission": settlement.total_commission,
                "total_chargebacks": settlement.chargeback_amount,
                "net_payable": settlement.net_payable,
                "status": settlement.status,
            },
        }

    @staticmethod
    def generate_settlement_pdf(db: Session, settlement_id: int) -> str:
        """
        Generate a settlement statement PDF and return the file path.
        """
        from app.services.pdf_service import PDFService
        import os

        settlement = db.get(Settlement, settlement_id)
        if not settlement:
            return None

        detail = SettlementService.get_transaction_detail(db, settlement_id)

        pdf_data = {
            "title": "Settlement Statement",
            "settlement_id": str(settlement.id),
            "month": settlement.settlement_month,
            "dealer_id": str(settlement.dealer_id),
            "total_revenue": f"{settlement.total_revenue:.2f}",
            "total_commission": f"{settlement.total_commission:.2f}",
            "chargebacks": f"{settlement.chargeback_amount:.2f}",
            "net_payable": f"{settlement.net_payable:.2f}",
            "status": settlement.status,
            "generated_at": settlement.created_at.isoformat(),
            "commission_line_items": str(len(detail["commission_items"])),
            "chargeback_line_items": str(len(detail["chargeback_items"])),
        }

        if settlement.paid_at:
            pdf_data["paid_at"] = settlement.paid_at.isoformat()
        if settlement.transaction_reference:
            pdf_data["payment_reference"] = settlement.transaction_reference

        os.makedirs("uploads/settlements", exist_ok=True)
        filename = f"settlement_{settlement.id}_{settlement.settlement_month}.pdf"
        path = f"uploads/settlements/{filename}"

        pdf = PDFService.generate_invoice(pdf_data)
        # PDFService returns a path string, but we build our own here
        from fpdf import FPDF

        doc = FPDF()
        doc.add_page()
        doc.set_font("Arial", "B", 16)
        doc.cell(200, 10, txt="Settlement Statement", ln=1, align="C")
        doc.set_font("Arial", size=10)
        for key, value in pdf_data.items():
            doc.cell(200, 8, txt=f"{key}: {value}", ln=1, align="L")
        doc.output(path)

        return path

    @staticmethod
    def get_dealer_payouts(db: Session, dealer_id: int) -> dict:
        """
        Returns payout schedule, next payout countdown, and tracking statuses.
        Uses dealer's payout_interval from DealerProfile.
        """
        now = datetime.now(UTC)

        # Get dealer profile for payout interval settings
        dealer_profile = db.exec(
            select(DealerProfile).where(DealerProfile.user_id == dealer_id)
        ).first()

        payout_interval = "Weekly"
        min_payout_amount = 0.0
        if dealer_profile:
            payout_interval = dealer_profile.payout_interval or "Weekly"
            min_payout_amount = dealer_profile.min_payout_amount or 0.0

        # Calculate next payout date based on interval
        interval_days = {"Daily": 1, "Weekly": 7, "Bi-Weekly": 14, "Monthly": 30}
        days_in_cycle = interval_days.get(payout_interval, 7)

        # Assume payouts start on the 1st of the month
        cycle_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        days_elapsed = (now - cycle_start).days
        cycles_passed = days_elapsed // days_in_cycle
        next_payout_date = cycle_start + timedelta(days=(cycles_passed + 1) * days_in_cycle)

        countdown_seconds = max(0, (next_payout_date - now).total_seconds())
        countdown_days = int(countdown_seconds // 86400)
        countdown_hours = int((countdown_seconds % 86400) // 3600)

        # Get all settlements for payout tracking
        settlements = db.exec(
            select(Settlement).where(
                Settlement.dealer_id == dealer_id,
            ).order_by(Settlement.created_at.desc())
        ).all()

        # Build payout list
        payouts = []
        for s in settlements:
            payouts.append({
                "id": s.id,
                "month": s.settlement_month,
                "amount": s.net_payable,
                "status": s.status,
                "due_date": s.due_date.isoformat() if s.due_date else None,
                "paid_at": s.paid_at.isoformat() if s.paid_at else None,
                "transaction_reference": s.transaction_reference,
            })

        # Summary by status
        status_counts = {}
        for s in settlements:
            status_counts[s.status] = status_counts.get(s.status, 0) + 1

        # Current cycle pending amount
        current_month = now.strftime("%Y-%m")
        pending_amount = sum(
            s.net_payable for s in settlements
            if s.status in ("pending", "generated") and s.settlement_month == current_month
        )

        return {
            "payout_interval": payout_interval,
            "min_payout_amount": min_payout_amount,
            "next_payout": {
                "date": next_payout_date.isoformat(),
                "countdown": {
                    "days": countdown_days,
                    "hours": countdown_hours,
                    "total_seconds": int(countdown_seconds),
                },
            },
            "current_cycle_pending": round(pending_amount, 2),
            "status_summary": status_counts,
            "payouts": payouts,
            "total": len(payouts),
        }
