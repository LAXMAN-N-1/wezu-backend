from __future__ import annotations
from sqlmodel import Session, select
from datetime import datetime, timezone; UTC = timezone.utc
from app.models.settlement_dispute import SettlementDispute
from app.models.settlement import Settlement
import logging

logger = logging.getLogger("wezu_disputes")


class DisputeService:

    @staticmethod
    def create_dispute(
        db: Session, settlement_id: int, dealer_id: int, reason: str
    ) -> SettlementDispute:
        """Open a dispute on a settlement."""
        settlement = db.get(Settlement, settlement_id)
        if not settlement:
            raise ValueError("Settlement not found")
        if settlement.dealer_id != dealer_id:
            raise PermissionError("You can only dispute your own settlements")

        # Check if an open dispute already exists
        existing = db.exec(
            select(SettlementDispute).where(
                SettlementDispute.settlement_id == settlement_id,
                SettlementDispute.status.in_(["open", "under_review"]),
            )
        ).first()
        if existing:
            raise ValueError("An open dispute already exists for this settlement")

        dispute = SettlementDispute(
            settlement_id=settlement_id,
            dealer_id=dealer_id,
            reason=reason,
            status="open",
        )
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        logger.info(
            f"Dispute #{dispute.id} opened for settlement {settlement_id} "
            f"by dealer {dealer_id}"
        )
        return dispute

    @staticmethod
    def resolve_dispute(
        db: Session,
        dispute_id: int,
        action: str,
        notes: str,
        adjustment_amount: float = 0.0,
    ) -> SettlementDispute:
        """
        Admin resolves a dispute.
        action: 'approve' (upheld, adjustment applied) or 'reject'.
        """
        dispute = db.get(SettlementDispute, dispute_id)
        if not dispute:
            raise ValueError("Dispute not found")
        if dispute.status not in ("open", "under_review"):
            raise ValueError("Dispute is already resolved")

        if action == "approve":
            dispute.status = "resolved"
            dispute.adjustment_amount = round(adjustment_amount, 2)
            # Adjust the linked settlement
            settlement = db.get(Settlement, dispute.settlement_id)
            if settlement:
                settlement.net_payable = round(
                    settlement.net_payable + adjustment_amount, 2
                )
                db.add(settlement)
        elif action == "reject":
            dispute.status = "rejected"
        else:
            raise ValueError("action must be 'approve' or 'reject'")

        dispute.resolution_notes = notes
        dispute.resolved_at = datetime.now(UTC)
        db.add(dispute)
        db.commit()
        db.refresh(dispute)

        logger.info(f"Dispute #{dispute_id} resolved: {action}")
        return dispute

    @staticmethod
    def list_open_disputes(db: Session) -> list:
        """List all open/under_review disputes for admin dashboard."""
        return db.exec(
            select(SettlementDispute).where(
                SettlementDispute.status.in_(["open", "under_review"])
            )
        ).all()
