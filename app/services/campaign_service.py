"""
Campaign Service — Business Logic
Targeting resolution, frequency capping, scheduling, analytics aggregation
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, func, col
from datetime import datetime, timedelta
from fastapi import HTTPException
from uuid import UUID
import logging

from app.models.campaign import (
    Campaign, CampaignTarget, CampaignSend,
    CampaignStatus, CampaignType, CampaignTargetRuleType,
)
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.rental import Rental
from app.models.notification import Notification
from app.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignTargetRuleCreate,
)

logger = logging.getLogger(__name__)


class CampaignService:
    """Promotional Campaign Engine business logic."""

    # ──────────────────── CRUD ────────────────────

    @staticmethod
    def create_campaign(
        db: Session, payload: CampaignCreate, created_by: int
    ) -> Campaign:
        """Create a new campaign in DRAFT status."""
        campaign = Campaign(
            name=payload.name,
            type=payload.type.value,
            message_title=payload.message_title,
            message_body=payload.message_body,
            promo_code_id=payload.promo_code_id,
            scheduled_at=payload.scheduled_at,
            frequency_cap=min(payload.frequency_cap, 3),  # hard cap
            target_criteria=payload.target_criteria,
            status=CampaignStatus.DRAFT,
            created_by=created_by,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        # Create targeting rules
        for rule in payload.targets:
            target = CampaignTarget(
                campaign_id=campaign.id,
                rule_type=rule.rule_type.value,
                rule_config=rule.rule_config,
            )
            db.add(target)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def get_campaign(db: Session, campaign_id: UUID) -> Campaign:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return campaign

    @staticmethod
    def list_campaigns(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> List[Campaign]:
        statement = select(Campaign).order_by(Campaign.created_at.desc())
        if status_filter:
            statement = statement.where(Campaign.status == status_filter)
        statement = statement.offset(skip).limit(limit)
        return list(db.exec(statement).all())

    @staticmethod
    def update_campaign(
        db: Session, campaign_id: UUID, payload: CampaignUpdate
    ) -> Campaign:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise HTTPException(
                status_code=400,
                detail="Only draft or paused campaigns can be updated",
            )

        update_data = payload.model_dump(exclude_unset=True)
        targets_data = update_data.pop("targets", None)

        for field, value in update_data.items():
            if value is not None:
                setattr(campaign, field, value)

        campaign.updated_at = datetime.utcnow()
        db.add(campaign)

        # Replace targeting rules if provided
        if targets_data is not None:
            # Delete existing targets
            existing = db.exec(
                select(CampaignTarget).where(
                    CampaignTarget.campaign_id == campaign_id
                )
            ).all()
            for t in existing:
                db.delete(t)

            for rule_data in targets_data:
                rule = CampaignTargetRuleCreate(**rule_data)
                target = CampaignTarget(
                    campaign_id=campaign_id,
                    rule_type=rule.rule_type.value,
                    rule_config=rule.rule_config,
                )
                db.add(target)

        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def delete_campaign(db: Session, campaign_id: UUID) -> dict:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise HTTPException(
                status_code=400,
                detail="Only draft or paused campaigns can be deleted",
            )

        # Delete related targets and sends
        targets = db.exec(
            select(CampaignTarget).where(CampaignTarget.campaign_id == campaign_id)
        ).all()
        for t in targets:
            db.delete(t)

        sends = db.exec(
            select(CampaignSend).where(CampaignSend.campaign_id == campaign_id)
        ).all()
        for s in sends:
            db.delete(s)

        db.delete(campaign)
        db.commit()
        return {"message": "Campaign deleted successfully"}

    # ──────────────────── Status Transitions ────────────────────

    @staticmethod
    def activate_campaign(db: Session, campaign_id: UUID) -> Campaign:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status != CampaignStatus.DRAFT:
            raise HTTPException(
                status_code=400, detail="Only draft campaigns can be activated"
            )

        # Non-birthday campaigns must have a schedule
        if campaign.type != CampaignType.BIRTHDAY and not campaign.scheduled_at:
            raise HTTPException(
                status_code=400,
                detail="Non-birthday campaigns require a scheduled_at datetime",
            )

        # Birthday campaigns go straight to active (processed by daily worker)
        if campaign.type == CampaignType.BIRTHDAY:
            campaign.status = CampaignStatus.ACTIVE
        else:
            campaign.status = CampaignStatus.SCHEDULED

        campaign.updated_at = datetime.utcnow()
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def pause_campaign(db: Session, campaign_id: UUID) -> Campaign:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status not in (CampaignStatus.ACTIVE, CampaignStatus.SCHEDULED):
            raise HTTPException(
                status_code=400,
                detail="Only active or scheduled campaigns can be paused",
            )

        campaign.status = CampaignStatus.PAUSED
        campaign.updated_at = datetime.utcnow()
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    # ──────────────────── Analytics ────────────────────

    @staticmethod
    def get_analytics(db: Session, campaign_id: UUID) -> dict:
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        sent = campaign.sent_count
        opened = campaign.opened_count
        converted = campaign.converted_count

        return {
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "sent_count": sent,
            "opened_count": opened,
            "converted_count": converted,
            "open_rate": round((opened / sent * 100), 2) if sent > 0 else 0.0,
            "conversion_rate": round((converted / sent * 100), 2) if sent > 0 else 0.0,
        }

    # ──────────────────── Targeting ────────────────────

    @staticmethod
    def resolve_targets(db: Session, campaign: Campaign) -> List[User]:
        """
        Resolve the set of users matching ALL targeting rules (AND logic).
        Returns a list of User objects that satisfy every CampaignTarget rule.
        """
        targets = db.exec(
            select(CampaignTarget).where(CampaignTarget.campaign_id == campaign.id)
        ).all()

        if not targets:
            # No rules → all active customers
            return list(
                db.exec(select(User).where(User.status == "active")).all()
            )

        # Start with all active users and progressively filter
        candidate_ids: Optional[set] = None

        for target in targets:
            matched_ids = CampaignService._resolve_single_rule(db, target)
            if candidate_ids is None:
                candidate_ids = matched_ids
            else:
                candidate_ids = candidate_ids & matched_ids

            # Short-circuit if no users match
            if not candidate_ids:
                return []

        if not candidate_ids:
            return []

        users = db.exec(
            select(User).where(col(User.id).in_(list(candidate_ids)))
        ).all()
        return list(users)

    @staticmethod
    def _resolve_single_rule(db: Session, target: CampaignTarget) -> set:
        """Resolve a single targeting rule and return matching user IDs."""
        config = target.rule_config or {}
        matched_ids: set = set()

        if target.rule_type == CampaignTargetRuleType.RENTAL_HISTORY:
            min_rentals = config.get("min_rentals", 1)
            results = db.exec(
                select(Rental.user_id, func.count(Rental.id).label("cnt"))
                .group_by(Rental.user_id)
                .having(func.count(Rental.id) >= min_rentals)
            ).all()
            matched_ids = {row[0] for row in results}

        elif target.rule_type == CampaignTargetRuleType.BIRTHDAY:
            today = datetime.utcnow().date()
            profiles = db.exec(
                select(UserProfile).where(UserProfile.date_of_birth.is_not(None))
            ).all()
            matched_ids = {
                p.user_id
                for p in profiles
                if p.date_of_birth
                and p.date_of_birth.month == today.month
                and p.date_of_birth.day == today.day
            }

        elif target.rule_type == CampaignTargetRuleType.LOCATION:
            city = config.get("city", "")
            if city:
                profiles = db.exec(
                    select(UserProfile).where(UserProfile.city == city)
                ).all()
                matched_ids = {p.user_id for p in profiles}

        elif target.rule_type == CampaignTargetRuleType.LAST_ACTIVITY:
            inactive_days = config.get("inactive_days", 30)
            cutoff = datetime.utcnow() - timedelta(days=inactive_days)
            users = db.exec(
                select(User).where(
                    User.status == "active",
                    User.last_login_at <= cutoff,
                )
            ).all()
            matched_ids = {u.id for u in users}

        elif target.rule_type == CampaignTargetRuleType.SPENDING_TIER:
            min_spend = config.get("min_spend", 0)
            max_spend = config.get("max_spend", 999999999)
            try:
                from app.models.financial import Transaction
                results = db.exec(
                    select(
                        Transaction.user_id,
                        func.sum(Transaction.amount).label("total"),
                    )
                    .where(Transaction.status == "completed")
                    .group_by(Transaction.user_id)
                    .having(func.sum(Transaction.amount) >= min_spend)
                    .having(func.sum(Transaction.amount) <= max_spend)
                ).all()
                matched_ids = {row[0] for row in results}
            except Exception as e:
                logger.warning(f"Spending tier resolution failed: {e}")

        return matched_ids

    # ──────────────────── Frequency Capping ────────────────────

    @staticmethod
    def check_frequency_cap(db: Session, user_id: int, cap: int = 3) -> bool:
        """
        Returns True if the user can receive another promo this week.
        Counts CampaignSend records in the last 7 days.
        """
        week_ago = datetime.utcnow() - timedelta(days=7)
        count = db.exec(
            select(func.count(CampaignSend.id)).where(
                CampaignSend.user_id == user_id,
                CampaignSend.sent_at >= week_ago,
            )
        ).one()
        return count < cap

    # ──────────────────── Send Logic ────────────────────

    @staticmethod
    def send_campaign(db: Session, campaign: Campaign) -> int:
        """
        Resolve targets → filter by frequency cap → send via NotificationService.
        Returns the number of users actually notified.
        """
        from app.services.notification_service import NotificationService

        users = CampaignService.resolve_targets(db, campaign)
        sent = 0

        for user in users:
            if not CampaignService.check_frequency_cap(
                db, user.id, campaign.frequency_cap
            ):
                continue

            # Send notification
            try:
                NotificationService.send_notification(
                    db,
                    user,
                    campaign.message_title,
                    campaign.message_body,
                    type="promo",
                    channel="push",
                    payload=f'{{"campaign_id": "{campaign.id}"}}',
                )
            except Exception as e:
                logger.error(
                    f"Failed to send campaign {campaign.id} to user {user.id}: {e}"
                )
                continue

            # Record the send
            send_record = CampaignSend(
                campaign_id=campaign.id,
                user_id=user.id,
            )
            db.add(send_record)
            sent += 1

        # Update counters
        campaign.sent_count += sent
        campaign.updated_at = datetime.utcnow()
        db.add(campaign)
        db.commit()

        return sent

    @staticmethod
    def send_test(db: Session, campaign_id: UUID, admin_user: User) -> dict:
        """Send a test notification for a campaign to the requesting admin only."""
        from app.services.notification_service import NotificationService

        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        NotificationService.send_notification(
            db,
            admin_user,
            f"[TEST] {campaign.message_title}",
            campaign.message_body,
            type="promo",
            channel="push",
            payload=f'{{"campaign_id": "{campaign.id}", "test": true}}',
        )

        return {"message": "Test notification sent to your account"}

    # ──────────────────── Worker Helpers ────────────────────

    @staticmethod
    def process_birthday_campaigns(db: Session) -> dict:
        """
        Find active birthday campaigns and send to users whose DOB matches today.
        Called by the daily worker.
        """
        campaigns = db.exec(
            select(Campaign).where(
                Campaign.type == CampaignType.BIRTHDAY,
                Campaign.status == CampaignStatus.ACTIVE,
            )
        ).all()

        total_sent = 0
        for campaign in campaigns:
            sent = CampaignService.send_campaign(db, campaign)
            total_sent += sent
            logger.info(
                f"Birthday campaign '{campaign.name}' sent to {sent} users"
            )

        return {
            "campaigns_processed": len(campaigns),
            "total_sent": total_sent,
        }

    @staticmethod
    def process_scheduled_campaigns(db: Session) -> dict:
        """
        Find scheduled campaigns whose scheduled_at has passed and execute send.
        Called by the periodic worker (every 15 minutes).
        """
        now = datetime.utcnow()
        campaigns = db.exec(
            select(Campaign).where(
                Campaign.status == CampaignStatus.SCHEDULED,
                Campaign.scheduled_at <= now,
            )
        ).all()

        total_sent = 0
        for campaign in campaigns:
            campaign.status = CampaignStatus.ACTIVE
            db.add(campaign)
            db.commit()

            sent = CampaignService.send_campaign(db, campaign)
            total_sent += sent

            campaign.status = CampaignStatus.COMPLETED
            campaign.updated_at = datetime.utcnow()
            db.add(campaign)
            db.commit()

            logger.info(
                f"Scheduled campaign '{campaign.name}' completed, sent to {sent} users"
            )

        return {
            "campaigns_processed": len(campaigns),
            "total_sent": total_sent,
        }
