import csv
import io
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlmodel import Session, select, func, col, desc
from fastapi import HTTPException

from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.station import Station
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


class DealerCampaignService:

    # ─── 1. CRUD Operations ───

    @staticmethod
    def create_campaign(db: Session, dealer_id: int, data: dict) -> DealerPromotion:
        """Create a new promotional campaign."""
        # Ensure code uniqueness
        code = data.get("promo_code", "").upper().strip()
        if db.exec(select(DealerPromotion).where(col(DealerPromotion.promo_code) == code)).first():
            raise HTTPException(status_code=400, detail="Promo code already exists")

        promo = DealerPromotion(
            dealer_id=dealer_id,
            name=data["name"],
            description=data.get("description"),
            promo_code=code,
            discount_type=data["discount_type"],
            discount_value=data["discount_value"],
            min_purchase_amount=data.get("min_purchase_amount"),
            max_discount_amount=data.get("max_discount_amount"),
            budget_limit=data.get("budget_limit"),
            daily_cap=data.get("daily_cap"),
            usage_limit_total=data.get("usage_limit_total"),
            usage_limit_per_user=data.get("usage_limit_per_user", 1),
            applicable_to=data.get("applicable_to", "ALL"),
            applicable_station_ids=json.dumps(data.get("applicable_station_ids", [])),
            start_date=data["start_date"],
            end_date=data["end_date"],
            is_active=data.get("is_active", True),
            # Default to auto-approve for dealers if policy allows, else False
            requires_approval=False, 
            approved_at=datetime.utcnow()
        )
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    @staticmethod
    def get_campaign(db: Session, promo_id: int, dealer_id: int) -> DealerPromotion:
        promo = db.exec(
            select(DealerPromotion).where(
                col(DealerPromotion.id) == promo_id,
                col(DealerPromotion.dealer_id) == dealer_id
            )
        ).first()
        if not promo:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return promo

    @staticmethod
    def list_campaigns(db: Session, dealer_id: int, active_only: bool = False) -> List[DealerPromotion]:
        stmt = select(DealerPromotion).where(col(DealerPromotion.dealer_id) == dealer_id)
        if active_only:
            stmt = stmt.where(col(DealerPromotion.is_active) == True)
        return list(db.exec(stmt).all())

    @staticmethod
    def update_campaign(db: Session, promo_id: int, dealer_id: int, data: dict) -> DealerPromotion:
        promo = DealerCampaignService.get_campaign(db, promo_id, dealer_id)
        
        # Don't allow changing the code to an existing one
        new_code = data.get("promo_code")
        if new_code and new_code.upper().strip() != promo.promo_code:
            existing = db.exec(select(DealerPromotion).where(col(DealerPromotion.promo_code) == new_code.upper().strip())).first()
            if existing:
                raise HTTPException(status_code=400, detail="Promo code already exists")
            promo.promo_code = new_code.upper().strip()

        for k, v in data.items():
            if k == "applicable_station_ids" and isinstance(v, list):
                setattr(promo, k, json.dumps(v))
            elif k != "promo_code" and hasattr(promo, k):
                setattr(promo, k, v)
        
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    @staticmethod
    def toggle_active(db: Session, promo_id: int, dealer_id: int, is_active: bool) -> DealerPromotion:
        promo = DealerCampaignService.get_campaign(db, promo_id, dealer_id)
        promo.is_active = is_active
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    @staticmethod
    def clone_campaign(db: Session, promo_id: int, dealer_id: int, new_code: str) -> DealerPromotion:
        original = DealerCampaignService.get_campaign(db, promo_id, dealer_id)
        
        code = new_code.upper().strip()
        if db.exec(select(DealerPromotion).where(col(DealerPromotion.promo_code) == code)).first():
            raise HTTPException(status_code=400, detail="Promo code already exists")

        new_promo = DealerPromotion(
            dealer_id=dealer_id,
            name=f"{original.name} (Copy)",
            description=original.description,
            promo_code=code,
            discount_type=original.discount_type,
            discount_value=original.discount_value,
            min_purchase_amount=original.min_purchase_amount,
            max_discount_amount=original.max_discount_amount,
            budget_limit=original.budget_limit,
            daily_cap=original.daily_cap,
            usage_limit_total=original.usage_limit_total,
            usage_limit_per_user=original.usage_limit_per_user,
            applicable_to=original.applicable_to,
            applicable_station_ids=original.applicable_station_ids,
            start_date=original.start_date,
            end_date=original.end_date,
            is_active=False, # Clones start inactive
            requires_approval=original.requires_approval
        )
        db.add(new_promo)
        db.commit()
        db.refresh(new_promo)
        return new_promo

    # ─── 2. Checkout Validation & Usage ───

    @staticmethod
    def validate_promo(
        db: Session, code: str, station_id: Optional[int], order_amount: float, user_id: int
    ) -> dict:
        """Full validation logic on checkout."""
        promo = db.exec(select(DealerPromotion).where(col(DealerPromotion.promo_code) == code)).first()
        if not promo:
            raise HTTPException(status_code=404, detail="Invalid promo code")

        # Track impression if it's just being checked/viewed
        # (Usually impressions are tracked via a separate endpoint, but we can incr here for simplicity or via an explicit `record_impression` method)

        if not promo.is_active:
            raise HTTPException(status_code=400, detail="Promo code is inactive")

        # Dates
        now = datetime.utcnow()
        # Convert start/end to datetime if they are date objects
        start = datetime.combine(promo.start_date, datetime.min.time()) if isinstance(promo.start_date, date) and not isinstance(promo.start_date, datetime) else promo.start_date
        end = datetime.combine(promo.end_date, datetime.max.time()) if isinstance(promo.end_date, date) and not isinstance(promo.end_date, datetime) else promo.end_date
        
        if now < start:
             raise HTTPException(status_code=400, detail="Promo code not yet valid")
        if now > end:
            raise HTTPException(status_code=400, detail="Promo code expired")

        # Station applicability
        if station_id and promo.applicable_station_ids:
            try:
                allowed_stations = json.loads(promo.applicable_station_ids)
                if allowed_stations and station_id not in allowed_stations:
                    raise HTTPException(status_code=400, detail="Promo code not applicable at this station")
            except Exception:
                pass

        # Minimum order
        if promo.min_purchase_amount and order_amount < promo.min_purchase_amount:
            raise HTTPException(status_code=400, detail=f"Minimum order amount is {promo.min_purchase_amount}")

        # Limits
        if promo.usage_limit_total and promo.usage_count >= promo.usage_limit_total:
            raise HTTPException(status_code=400, detail="Promo code global usage limit reached")

        # Budget Check
        if promo.budget_limit:
            if getattr(promo, "total_discount_given", 0.0) >= promo.budget_limit:
                 raise HTTPException(status_code=400, detail="Promo code budget exhausted")

        # Daily Cap Check
        if promo.daily_cap:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_uses = db.exec(
                select(func.count(col(PromotionUsage.id))).where(
                    col(PromotionUsage.promotion_id) == promo.id,
                    col(PromotionUsage.used_at) >= today_start
                )
            ).one() or 0
            if daily_uses >= promo.daily_cap:
                 raise HTTPException(status_code=400, detail="Promo code daily usage cap reached")

        # Per-user limit
        user_uses = db.exec(
            select(func.count(col(PromotionUsage.id))).where(
                col(PromotionUsage.promotion_id) == promo.id,
                col(PromotionUsage.user_id) == user_id
            )
        ).one() or 0
        if user_uses >= promo.usage_limit_per_user:
             raise HTTPException(status_code=400, detail="You have reached your usage limit for this code")

        # Calculate discount
        discount = 0.0
        discount_type = promo.discount_type.upper() if promo.discount_type else ""
        if discount_type == "PERCENTAGE":
            discount = (promo.discount_value / 100) * order_amount
        elif discount_type == "FIXED_AMOUNT":
             discount = promo.discount_value
        elif discount_type == "FREE_DELIVERY":
             discount = min(order_amount, promo.discount_value) # Assuming value is the max delivery fee covered

        if promo.max_discount_amount:
            discount = min(discount, promo.max_discount_amount)
            
        # Ensure we don't exceed remaining budget if budget_limit exists
        if promo.budget_limit:
            remaining_budget = promo.budget_limit - getattr(promo, "total_discount_given", 0.0)
            discount = min(discount, remaining_budget)

        final_amount = max(0, order_amount - discount)

        return {
            "code": promo.promo_code,
            "discount_applied": round(float(discount), 2),
            "final_amount": round(float(final_amount), 2),
            "promo_id": promo.id
        }

    @staticmethod
    def apply_promo(
        db: Session, promo_id: int, user_id: int, order_amount: float, 
        discount_applied: float, final_amount: float
    ) -> PromotionUsage:
        """Record the usage of a promo code when an order is finalized."""
        promo = db.get(DealerPromotion, promo_id)
        if not promo:
            raise HTTPException(status_code=404, detail="Promo not found")

        assert promo.id is not None
        usage = PromotionUsage(
            promotion_id=promo.id,
            user_id=user_id,
            discount_applied=discount_applied,
            original_amount=order_amount,
            final_amount=final_amount,
            used_at=datetime.utcnow()
        )
        db.add(usage)

        # Update counters
        promo.usage_count += 1
        if not hasattr(promo, "total_discount_given"):
             promo.total_discount_given = 0.0
        promo.total_discount_given += discount_applied

        db.add(promo)
        db.commit()
        db.refresh(usage)
        return usage

    @staticmethod
    def record_impression(db: Session, promo_id: int):
        """Increment impressions counter."""
        promo = db.get(DealerPromotion, promo_id)
        if promo:
            promo.impressions = getattr(promo, "impressions", 0) + 1
            db.add(promo)
            db.commit()

    # ─── 3. Analytics ───

    @staticmethod
    def get_analytics(db: Session, promo_id: int, dealer_id: int) -> dict:
        promo = DealerCampaignService.get_campaign(db, promo_id, dealer_id)

        usages = db.exec(
            select(PromotionUsage).where(col(PromotionUsage.promotion_id) == promo.id)
        ).all()

        total_orders = len(usages)
        total_discount = sum(u.discount_applied for u in usages)
        total_revenue = sum(u.final_amount for u in usages)
        
        # Calculate ROI: (Net Revenue - Discount Cost) / Discount Cost
        # Since discount is the "cost" of the campaign
        roi = 0.0
        if total_discount > 0:
            roi = ((total_revenue - total_discount) / total_discount) * 100

        impressions = getattr(promo, "impressions", 0)
        conversion_rate = (total_orders / impressions * 100) if impressions > 0 else 0.0

        return {
            "campaign_name": promo.name,
            "code": promo.promo_code,
            "impressions": impressions,
            "usage_count": total_orders,
            "conversion_rate_pct": round(float(conversion_rate), 2),
            "total_discount_given": round(float(total_discount), 2),
            "additional_revenue_driven": round(float(total_revenue), 2),
            "roi_pct": round(float(roi), 2),
            "status": "Active" if promo.is_active else "Inactive",
            "budget_used_pct": round((total_discount / promo.budget_limit * 100), 1) if promo.budget_limit else None
        }

    # ─── 4. Bulk Operations ───

    @staticmethod
    def bulk_create_from_csv(db: Session, dealer_id: int, csv_content: str) -> dict:
        """Parse CSV and create campaigns. Returns counts."""
        reader = csv.DictReader(io.StringIO(csv_content))
        created = 0
        errors = []

        now = datetime.utcnow()
        DEFAULT_END = now + __import__("datetime").timedelta(days=30)
        
        for idx, row in enumerate(reader):
            try:
                code = row.get("promo_code", "").upper().strip()
                if not code:
                    errors.append(f"Row {idx+1}: Missing promo_code")
                    continue
                    
                # Skip if exists
                if db.exec(select(DealerPromotion).where(col(DealerPromotion.promo_code) == code)).first():
                    errors.append(f"Row {idx+1}: Code {code} already exists")
                    continue

                # Handle station IDs pipe-delimited list like '1|2'
                stations = row.get("applicable_station_ids", "").strip()
                applicable_stations = json.dumps([int(s) for s in stations.split("|") if s.isdigit()]) if stations else "[]"

                promo = DealerPromotion(
                    dealer_id=dealer_id,
                    name=row.get("name", f"Bulk Campaign {code}"),
                    description=row.get("description"),
                    promo_code=code,
                    discount_type=row.get("discount_type", "PERCENTAGE"),
                    discount_value=float(row.get("discount_value", 10)),
                    min_purchase_amount=float(row.get("min_purchase_amount", 0)) or None,
                    max_discount_amount=float(row.get("max_discount_amount", 0)) or None,
                    budget_limit=float(row.get("budget_limit", 0)) or None,
                    usage_limit_total=int(row.get("usage_limit_total", 0)) or None,
                    applicable_station_ids=applicable_stations,
                    start_date=datetime.fromisoformat(row["start_date"]) if row.get("start_date") else now,
                    end_date=datetime.fromisoformat(row["end_date"]) if row.get("end_date") else DEFAULT_END,
                    is_active=True,
                    requires_approval=False,
                    approved_at=now
                )
                db.add(promo)
                created += 1
            except Exception as e:
                errors.append(f"Row {idx+1}: {str(e)}")

        if created > 0:
            db.commit()

        return {
            "created": created,
            "errors": errors
        }

    @staticmethod
    def bulk_toggle(db: Session, dealer_id: int, promo_ids: List[int], is_active: bool) -> int:
        """Toggle active status for multiple campaigns. Returns count of updated."""
        promos = db.exec(
            select(DealerPromotion).where(
                col(DealerPromotion.dealer_id) == dealer_id,
                col(DealerPromotion.id).in_(promo_ids)
            )
        ).all()
        
        count = 0
        for p in promos:
            p.is_active = is_active
            db.add(p)
            count += 1
            
        if count > 0:
            db.commit()
            
        return count
class AdminCampaignService:
    """Promotional Campaign Engine business logic."""

    # ──────────────────── CRUD ────────────────────

    @staticmethod
    def create_campaign(
        db: Session, payload: CampaignCreate, created_by: int
    ) -> Campaign:
        """Create a new campaign in DRAFT status."""
        campaign = Campaign(
            name=payload.name,
            type=CampaignType(payload.type.value),
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
                rule_type=CampaignTargetRuleType(rule.rule_type.value),
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
        statement = select(Campaign).order_by(desc(Campaign.created_at))
        if status_filter:
            statement = statement.where(col(Campaign.status) == status_filter)
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
                    col(CampaignTarget.campaign_id) == campaign_id
                )
            ).all()
            for t in existing:
                db.delete(t)

            for rule_data in targets_data:
                rule = CampaignTargetRuleCreate(**rule_data)
                target = CampaignTarget(
                    campaign_id=campaign_id,
                    rule_type=CampaignTargetRuleType(rule.rule_type.value),
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
            select(CampaignTarget).where(col(CampaignTarget.campaign_id) == campaign_id)
        ).all()
        for t in targets:
            db.delete(t)

        sends = db.exec(
            select(CampaignSend).where(col(CampaignSend.campaign_id) == campaign_id)
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
            select(CampaignTarget).where(col(CampaignTarget.campaign_id) == campaign.id)
        ).all()

        if not targets:
            # No rules → all active customers
            return list(
                db.exec(select(User).where(col(User.status) == "active")).all()
            )

        # Start with all active users and progressively filter
        candidate_ids: Optional[set] = None

        for target in targets:
            matched_ids = AdminCampaignService._resolve_single_rule(db, target)
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
                select(Rental.user_id, func.count(col(Rental.id)).label("cnt"))
                .group_by(col(Rental.user_id))
                .having(func.count(col(Rental.id)) >= min_rentals)
            ).all()
            matched_ids = {row[0] for row in results}

        elif target.rule_type == CampaignTargetRuleType.BIRTHDAY:
            today = datetime.utcnow().date()
            profiles = db.exec(
                select(UserProfile).where(col(UserProfile.date_of_birth).is_not(None))
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
                    select(UserProfile).where(col(UserProfile.city) == city)
                ).all()
                matched_ids = {p.user_id for p in profiles}

        elif target.rule_type == CampaignTargetRuleType.LAST_ACTIVITY:
            inactive_days = config.get("inactive_days", 30)
            cutoff = datetime.utcnow() - timedelta(days=inactive_days)
            users = db.exec(
                select(User).where(
                    col(User.status) == "active",
                    col(User.last_login) <= cutoff,
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
                        func.sum(col(Transaction.amount)).label("total"),
                    )
                    .where(col(Transaction.status) == "completed")
                    .group_by(col(Transaction.user_id))
                    .having(func.sum(col(Transaction.amount)) >= min_spend)
                    .having(func.sum(col(Transaction.amount)) <= max_spend)
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
            select(func.count(col(CampaignSend.id))).where(
                col(CampaignSend.user_id) == user_id,
                col(CampaignSend.sent_at) >= week_ago,
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

        users = AdminCampaignService.resolve_targets(db, campaign)
        sent = 0

        for user in users:
            assert user.id is not None
            if not AdminCampaignService.check_frequency_cap(
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
                col(Campaign.type) == CampaignType.BIRTHDAY,
                col(Campaign.status) == CampaignStatus.ACTIVE,
            )
        ).all()

        total_sent = 0
        for campaign in campaigns:
            sent = AdminCampaignService.send_campaign(db, campaign)
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
                col(Campaign.status) == CampaignStatus.SCHEDULED,
                col(Campaign.scheduled_at) <= now,
            )
        ).all()

        total_sent = 0
        for campaign in campaigns:
            campaign.status = CampaignStatus.ACTIVE
            db.add(campaign)
            db.commit()

            sent = AdminCampaignService.send_campaign(db, campaign)
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
