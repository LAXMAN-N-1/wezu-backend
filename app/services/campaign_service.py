"""
Dealer Campaign Service — Manage promotional campaigns, validate at checkout,
collect analytics, and handle bulk operations.
"""

import csv
import io
import json
import logging
import uuid
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from sqlmodel import Session, select, func, col
from fastapi import HTTPException

from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.station import Station
# Using a generic "order" table name or whatever represents the transaction

logger = logging.getLogger(__name__)


class CampaignService:

    # ─── 1. CRUD Operations ───

    @staticmethod
    def create_campaign(db: Session, dealer_id: int, data: dict) -> DealerPromotion:
        """Create a new promotional campaign."""
        # Ensure code uniqueness
        code = data.get("promo_code", "").upper().strip()
        if db.exec(select(DealerPromotion).where(DealerPromotion.promo_code == code)).first():
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
                DealerPromotion.id == promo_id,
                DealerPromotion.dealer_id == dealer_id
            )
        ).first()
        if not promo:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return promo

    @staticmethod
    def list_campaigns(db: Session, dealer_id: int, active_only: bool = False) -> List[DealerPromotion]:
        stmt = select(DealerPromotion).where(DealerPromotion.dealer_id == dealer_id)
        if active_only:
            stmt = stmt.where(DealerPromotion.is_active == True)
        return list(db.exec(stmt).all())

    @staticmethod
    def update_campaign(db: Session, promo_id: int, dealer_id: int, data: dict) -> DealerPromotion:
        promo = CampaignService.get_campaign(db, promo_id, dealer_id)
        
        # Don't allow changing the code to an existing one
        new_code = data.get("promo_code")
        if new_code and new_code.upper().strip() != promo.promo_code:
            existing = db.exec(select(DealerPromotion).where(DealerPromotion.promo_code == new_code.upper().strip())).first()
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
        promo = CampaignService.get_campaign(db, promo_id, dealer_id)
        promo.is_active = is_active
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    @staticmethod
    def clone_campaign(db: Session, promo_id: int, dealer_id: int, new_code: str) -> DealerPromotion:
        original = CampaignService.get_campaign(db, promo_id, dealer_id)
        
        code = new_code.upper().strip()
        if db.exec(select(DealerPromotion).where(DealerPromotion.promo_code == code)).first():
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
        promo = db.exec(select(DealerPromotion).where(DealerPromotion.promo_code == code)).first()
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
                select(func.count(PromotionUsage.id)).where(
                    PromotionUsage.promotion_id == promo.id,
                    PromotionUsage.used_at >= today_start
                )
            ).one() or 0
            if daily_uses >= promo.daily_cap:
                 raise HTTPException(status_code=400, detail="Promo code daily usage cap reached")

        # Per-user limit
        user_uses = db.exec(
            select(func.count(PromotionUsage.id)).where(
                PromotionUsage.promotion_id == promo.id,
                PromotionUsage.user_id == user_id
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
        promo = CampaignService.get_campaign(db, promo_id, dealer_id)

        usages = db.exec(
            select(PromotionUsage).where(PromotionUsage.promotion_id == promo.id)
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
                if db.exec(select(DealerPromotion).where(DealerPromotion.promo_code == code)).first():
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
                DealerPromotion.dealer_id == dealer_id,
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
