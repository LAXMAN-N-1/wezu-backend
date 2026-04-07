"""
Dealer Portal Dashboard — Aggregated KPIs, alerts, and activity feed.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from datetime import datetime, UTC, timedelta
from sqlalchemy import case

from app.db.session import get_session
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station
from app.models.dealer_inventory import DealerInventory
from app.models.support import SupportTicket, TicketStatus
from app.models.notification import Notification
from app.models.rental import Rental
from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.utils.runtime_cache import cached_call

router = APIRouter()


def _get_dealer(db: Session, user_id: int) -> DealerProfile:
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    return dealer


def _dealer_dashboard_cache(user_id: int, cache_key: str, call, *parts: Any) -> Any:
    return cached_call(
        "dealer-dashboard",
        user_id,
        cache_key,
        *parts,
        ttl_seconds=settings.DEALER_PORTAL_CACHE_TTL_SECONDS,
        call=call,
    )


@router.get("/dashboard")
def get_dashboard_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Aggregated dashboard KPIs for dealer portal."""
    def _build_summary() -> dict[str, Any]:
        dealer = _get_dealer(db, current_user.id)

        station_metrics = db.exec(
            select(
                func.count(Station.id),
                func.coalesce(
                    func.sum(
                        case(
                            (Station.status == "active", 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.avg(case((Station.rating > 0, Station.rating), else_=None)),
            ).where(Station.dealer_id == dealer.id)
        ).one()

        inventory = db.exec(
            select(DealerInventory).where(DealerInventory.dealer_id == dealer.id)
        ).all()
        total_batteries = sum(i.quantity_available for i in inventory)
        total_damaged = sum(i.quantity_damaged for i in inventory)

        active_rentals = db.exec(
            select(func.count(Rental.id))
            .join(Station, Rental.start_station_id == Station.id)
            .where(
                Station.dealer_id == dealer.id,
                Rental.status == "active",
            )
        ).one() or 0

        revenue_this_month = 0.0
        try:
            from app.models.commission import CommissionLog

            now = datetime.now(UTC)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            revenue_this_month = db.exec(
                select(func.coalesce(func.sum(CommissionLog.amount), 0.0)).where(
                    CommissionLog.dealer_id == dealer.id,
                    CommissionLog.created_at >= month_start,
                )
            ).one() or 0.0
        except Exception:
            pass

        open_tickets = db.exec(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.user_id == current_user.id,
                SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
            )
        ).one() or 0

        total_stations = int(station_metrics[0] or 0)
        active_stations = int(station_metrics[1] or 0)
        avg_rating = round(float(station_metrics[2] or 0.0), 1) if total_stations else 0.0

        return {
            "total_batteries": total_batteries,
            "total_damaged": total_damaged,
            "active_rentals": active_rentals,
            "revenue_this_month": float(revenue_this_month),
            "total_stations": total_stations,
            "active_stations": active_stations,
            "open_tickets": open_tickets,
            "customer_satisfaction": avg_rating,
            "inventory_summary": [
                {
                    "battery_model": i.battery_model,
                    "available": i.quantity_available,
                    "reserved": i.quantity_reserved,
                    "damaged": i.quantity_damaged,
                }
                for i in inventory
            ],
        }

    return _dealer_dashboard_cache(current_user.id, "summary", _build_summary)


@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Consolidated alerts for dealer portal: low stock, maintenance, tickets."""
    def _build_alerts() -> dict[str, Any]:
        dealer = _get_dealer(db, current_user.id)
        alerts = []

        inventory = db.exec(
            select(DealerInventory).where(DealerInventory.dealer_id == dealer.id)
        ).all()
        for inv in inventory:
            if inv.quantity_available <= inv.reorder_level:
                alerts.append({
                    "type": "low_stock",
                    "severity": "critical" if inv.quantity_available == 0 else "warning",
                    "title": f"Low stock: {inv.battery_model}",
                    "message": f"Only {inv.quantity_available} units available (reorder at {inv.reorder_level})",
                    "data": {"inventory_id": inv.id, "battery_model": inv.battery_model},
                })

        stations = db.exec(
            select(Station).where(Station.dealer_id == dealer.id)
        ).all()
        for station in stations:
            if station.last_maintenance_date:
                days_since = (datetime.now(UTC).replace(tzinfo=None) - station.last_maintenance_date).days
                if days_since > 30:
                    alerts.append({
                        "type": "maintenance_due",
                        "severity": "warning",
                        "title": f"Maintenance overdue: {station.name}",
                        "message": f"Last maintenance was {days_since} days ago",
                        "data": {"station_id": station.id},
                    })

        tickets = db.exec(
            select(SupportTicket).where(
                SupportTicket.user_id == current_user.id,
                SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
            )
        ).all()
        for ticket in tickets:
            alerts.append({
                "type": "ticket",
                "severity": ticket.priority.value if ticket.priority else "medium",
                "title": f"Ticket #{ticket.id}: {ticket.subject}",
                "message": f"Status: {ticket.status.value}",
                "data": {"ticket_id": ticket.id},
            })

        return {"alerts": alerts, "total": len(alerts)}

    return _dealer_dashboard_cache(current_user.id, "alerts", _build_alerts)


@router.get("/activity")
def get_activity_feed(
    limit: int = 20,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Recent activity feed for dealer dashboard."""
    def _build_activity() -> dict[str, Any]:
        _get_dealer(db, current_user.id)
        notifications = db.exec(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()

        activities = [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": str(n.created_at),
            }
            for n in notifications
        ]
        return {"data": activities, "total": len(activities)}

    return _dealer_dashboard_cache(current_user.id, "activity", _build_activity, limit)


@router.get("/customers")
def get_customers_list(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get the list of unique customers who rented from the dealer's stations."""
    dealer = _get_dealer(db, current_user.id)
    
    # Single query: users + rental count via GROUP BY (replaces N+1)
    statement = (
        select(User, func.count(Rental.id).label("rental_count"))
        .join(Rental, Rental.user_id == User.id)
        .join(Station, Rental.start_station_id == Station.id)
        .where(Station.dealer_id == dealer.id)
        .group_by(User.id)
    )
    rows = db.exec(statement).all()
    
    data = []
    for u, rental_count in rows:
        data.append({
            "id": u.id,
            "name": u.full_name or (u.email.split('@')[0] if u.email else "Unknown"),
            "email": u.email,
            "phone": u.phone_number or "N/A",
            "total_rentals": rental_count or 0,
            "status": "Active" if u.is_active else "Inactive",
            "joined_at": str(u.created_at) if hasattr(u, 'created_at') and u.created_at else None
        })
        
    return {"data": data, "total": len(data)}


@router.get("/campaigns")
def get_dealer_campaigns(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer campaign feed with lifecycle status and performance metrics."""

    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def _derive_status(
        *,
        start: datetime | None,
        end: datetime | None,
        is_active: bool,
        requires_approval: bool,
        approved_at: datetime | None,
        now_naive_utc: datetime,
    ) -> str:
        if requires_approval and not approved_at:
            return "Pending Approval"
        if end and now_naive_utc > end:
            return "Expired"
        if start and now_naive_utc < start:
            return "Scheduled"
        if not is_active:
            return "Paused"
        return "Active"

    def _build_campaigns() -> dict[str, Any]:
        dealer = _get_dealer(db, current_user.id)
        campaigns = db.exec(
            select(DealerPromotion)
            .where(DealerPromotion.dealer_id == dealer.id)
            .order_by(DealerPromotion.created_at.desc())
        ).all()

        usage_rows = db.exec(
            select(
                PromotionUsage.promotion_id,
                func.count(PromotionUsage.id),
                func.coalesce(func.sum(PromotionUsage.final_amount), 0.0),
                func.coalesce(func.sum(PromotionUsage.discount_applied), 0.0),
            )
            .join(DealerPromotion, DealerPromotion.id == PromotionUsage.promotion_id)
            .where(DealerPromotion.dealer_id == dealer.id)
            .group_by(PromotionUsage.promotion_id)
        ).all()
        usage_map = {
            int(promo_id): {
                "redemptions": int(redemptions or 0),
                "revenue": float(revenue or 0.0),
                "discount_given": float(discount_given or 0.0),
            }
            for promo_id, redemptions, revenue, discount_given in usage_rows
        }

        now_naive_utc = datetime.now(UTC).replace(tzinfo=None)
        data: list[dict[str, Any]] = []
        status_counts = {
            "active": 0,
            "scheduled": 0,
            "expired": 0,
            "paused": 0,
            "pending_approval": 0,
        }
        total_redemptions = 0
        total_revenue = 0.0
        total_discount_given = 0.0

        for campaign in campaigns:
            usage = usage_map.get(int(campaign.id or 0), {"redemptions": 0, "revenue": 0.0, "discount_given": 0.0})
            start = _normalize_datetime(campaign.start_date)
            end = _normalize_datetime(campaign.end_date)
            approved_at = _normalize_datetime(campaign.approved_at)
            status = _derive_status(
                start=start,
                end=end,
                is_active=bool(campaign.is_active),
                requires_approval=bool(campaign.requires_approval),
                approved_at=approved_at,
                now_naive_utc=now_naive_utc,
            )

            budget_used_pct = None
            if campaign.budget_limit and campaign.budget_limit > 0:
                budget_used_pct = round((usage["discount_given"] / float(campaign.budget_limit)) * 100.0, 2)

            impressions = int(campaign.impressions or 0)
            conversion_rate_pct = round((usage["redemptions"] / impressions) * 100.0, 2) if impressions > 0 else 0.0

            data.append(
                {
                    "id": campaign.id,
                    "title": campaign.name,
                    "desc": campaign.description,
                    "promo_code": campaign.promo_code,
                    "status": status,
                    "is_active": bool(campaign.is_active),
                    "dates": {
                        "start": campaign.start_date.isoformat() if campaign.start_date else None,
                        "end": campaign.end_date.isoformat() if campaign.end_date else None,
                    },
                    "redemptions": usage["redemptions"],
                    "revenue": round(usage["revenue"], 2),
                    "discount_given": round(usage["discount_given"], 2),
                    "impressions": impressions,
                    "conversion_rate_pct": conversion_rate_pct,
                    "budget_limit": float(campaign.budget_limit) if campaign.budget_limit is not None else None,
                    "budget_used_pct": budget_used_pct,
                    "usage_limit_total": campaign.usage_limit_total,
                    "usage_limit_per_user": campaign.usage_limit_per_user,
                    "discount_type": campaign.discount_type,
                    "discount_value": float(campaign.discount_value),
                    "applicable_to": campaign.applicable_to,
                }
            )

            total_redemptions += usage["redemptions"]
            total_revenue += usage["revenue"]
            total_discount_given += usage["discount_given"]

            if status == "Active":
                status_counts["active"] += 1
            elif status == "Scheduled":
                status_counts["scheduled"] += 1
            elif status == "Expired":
                status_counts["expired"] += 1
            elif status == "Paused":
                status_counts["paused"] += 1
            elif status == "Pending Approval":
                status_counts["pending_approval"] += 1

        return {
            "data": data,
            "total": len(data),
            "summary": {
                "active_campaigns": status_counts["active"],
                "scheduled_campaigns": status_counts["scheduled"],
                "expired_campaigns": status_counts["expired"],
                "paused_campaigns": status_counts["paused"],
                "pending_approval_campaigns": status_counts["pending_approval"],
                "total_redemptions": total_redemptions,
                "total_revenue": round(total_revenue, 2),
                "total_discount_given": round(total_discount_given, 2),
            },
        }

    return _dealer_dashboard_cache(current_user.id, "campaigns", _build_campaigns)

@router.get("/profile")
def get_dealer_profile_details(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get the dealer's profile details."""
    dealer = _get_dealer(db, current_user.id)
    return {"data": dealer.dict(), "success": True}

# ── Documents ────────────────────────────────────────────────

@router.get("/documents")
def list_dealer_documents(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all documents for the dealer."""
    dealer = _get_dealer(db, current_user.id)
    from app.models.dealer import DealerDocument
    docs = db.exec(
        select(DealerDocument).where(
            DealerDocument.dealer_id == dealer.id,
            DealerDocument.status != "ARCHIVED",
        )
    ).all()

    data = []
    for d in docs:
        data.append({
            "id": d.id,
            "document_type": d.document_type,
            "category": d.category or "verification",
            "file_url": d.file_url,
            "status": d.status,
            "version": d.version,
            "valid_until": str(d.valid_until) if d.valid_until else None,
            "created_at": str(d.uploaded_at) if d.uploaded_at else None,
        })
    return {"data": data, "total": len(data)}


@router.post("/documents/upload")
def upload_dealer_document(
    data: "DealerDocumentUpload",
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload a new document or a newer version of an existing document."""
    from app.schemas.input_contracts import DealerDocumentUpload
    dealer = _get_dealer(db, current_user.id)
    from app.models.dealer import DealerDocument

    document_type = data.document_type
    category = data.category
    file_url = data.file_url
    valid_until_str = data.valid_until

    # Find existing and determine next version
    existing_docs = db.exec(
        select(DealerDocument).where(
            DealerDocument.dealer_id == dealer.id,
            DealerDocument.document_type == document_type,
        )
    ).all()

    next_version = 1
    if existing_docs:
        for doc in existing_docs:
            if doc.status != "ARCHIVED":
                doc.status = "ARCHIVED"
        highest = max(d.version for d in existing_docs)
        next_version = highest + 1

    valid_until = None
    if valid_until_str:
        try:
            valid_until = datetime.fromisoformat(valid_until_str)
        except Exception:
            pass

    new_doc = DealerDocument(
        dealer_id=dealer.id,
        document_type=document_type,
        category=category,
        file_url=file_url,
        version=next_version,
        status="PENDING",
        valid_until=valid_until,
        is_verified=False,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    return {"message": "Document uploaded successfully", "id": new_doc.id, "version": next_version}


# ── Transactions / Revenue ───────────────────────────────────

@router.get("/transactions")
def get_dealer_transactions(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get rental transactions (revenue) for the dealer's stations."""
    dealer = _get_dealer(db, current_user.id)
    stations = db.exec(
        select(Station).where(Station.dealer_id == dealer.id)
    ).all()
    station_ids = [s.id for s in stations]

    if not station_ids:
        return {"data": [], "total": 0}

    rentals = db.exec(
        select(Rental)
        .where(Rental.start_station_id.in_(station_ids))
        .order_by(Rental.created_at.desc())
        .limit(100)
    ).all()

    # Batch-load users + stations (eliminates 2 N+1 queries per rental)
    user_ids = list({r.user_id for r in rentals if r.user_id})
    stn_ids = list({r.start_station_id for r in rentals if r.start_station_id})
    users_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    stations_map = {s.id: s for s in db.exec(select(Station).where(Station.id.in_(stn_ids))).all()} if stn_ids else {}

    data = []
    for r in rentals:
        customer = users_map.get(r.user_id)
        station = stations_map.get(r.start_station_id)
        data.append({
            "id": r.id,
            "transaction_type": "Rental",
            "amount": float(r.total_amount or 0),
            "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
            "created_at": str(r.created_at),
            "description": f"{customer.full_name if customer else 'Customer'} at {station.name if station else 'Station'}",
        })

    return {"data": data, "total": len(data)}
