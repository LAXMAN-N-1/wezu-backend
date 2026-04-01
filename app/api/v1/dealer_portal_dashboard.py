"""
Dealer Portal Dashboard — Aggregated KPIs, alerts, and activity feed.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from datetime import datetime, UTC, timedelta

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station
from app.models.dealer_inventory import DealerInventory
from app.models.support import SupportTicket, TicketStatus
from app.models.notification import Notification
from app.models.rental import Rental

router = APIRouter()


def _get_dealer(db: Session, user_id: int) -> DealerProfile:
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    return dealer


@router.get("/dashboard")
def get_dashboard_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Aggregated dashboard KPIs for dealer portal."""
    dealer = _get_dealer(db, current_user.id)

    stations = db.exec(
        select(Station).where(Station.dealer_id == dealer.id)
    ).all()
    station_ids = [s.id for s in stations]

    # KPI 1: Total batteries in stock
    inventory = db.exec(
        select(DealerInventory).where(DealerInventory.dealer_id == dealer.id)
    ).all()
    total_batteries = sum(i.quantity_available for i in inventory)
    total_damaged = sum(i.quantity_damaged for i in inventory)

    # KPI 2: Active rentals today
    active_rentals = 0
    try:
        active_rentals = db.exec(
            select(func.count(Rental.id)).where(
                Rental.start_station_id.in_(station_ids),
                Rental.status == "active",
            )
        ).one() or 0
    except Exception:
        pass

    # KPI 3: Revenue this month
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

    # KPI 4: Station count
    total_stations = len(stations)
    active_stations = len([s for s in stations if s.status in ("active", "OPERATIONAL")])

    # KPI 5: Open tickets
    open_tickets = db.exec(
        select(func.count(SupportTicket.id)).where(
            SupportTicket.user_id == current_user.id,
            SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
        )
    ).one() or 0

    # KPI 6: Customer satisfaction (placeholder)
    avg_rating = 0.0
    if stations:
        ratings = [s.rating for s in stations if s.rating > 0]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

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


@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Consolidated alerts for dealer portal: low stock, maintenance, tickets."""
    dealer = _get_dealer(db, current_user.id)
    alerts = []

    # Low stock alerts
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

    # Maintenance alerts
    stations = db.exec(
        select(Station).where(Station.dealer_id == dealer.id)
    ).all()
    for station in stations:
        if station.last_maintenance_date:
            days_since = (datetime.utcnow() - station.last_maintenance_date).days
            if days_since > 30:
                alerts.append({
                    "type": "maintenance_due",
                    "severity": "warning",
                    "title": f"Maintenance overdue: {station.name}",
                    "message": f"Last maintenance was {days_since} days ago",
                    "data": {"station_id": station.id},
                })

    # Open ticket alerts
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


@router.get("/activity")
def get_activity_feed(
    limit: int = 20,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Recent activity feed for dealer dashboard."""
    dealer = _get_dealer(db, current_user.id)
    activities = []

    # Recent notifications
    notifications = db.exec(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()

    for n in notifications:
        activities.append({
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": str(n.created_at),
        })

    return {"data": activities, "total": len(activities)}


@router.get("/customers")
def get_customers_list(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get the list of unique customers who rented from the dealer's stations."""
    dealer = _get_dealer(db, current_user.id)
    
    statement = (
        select(User)
        .join(Rental, Rental.user_id == User.id)
        .join(Station, Rental.start_station_id == Station.id)
        .where(Station.dealer_id == dealer.id)
        .distinct()
    )
    users = db.exec(statement).all()
    
    data = []
    for u in users:
        rental_count = db.exec(
            select(func.count(Rental.id))
            .join(Station, Rental.start_station_id == Station.id)
            .where(Station.dealer_id == dealer.id, Rental.user_id == u.id)
        ).one_or_none()
        
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
    """Mock endpoint for Dealer Campaigns since the DB schema is currently empty."""
    dealer = _get_dealer(db, current_user.id)
    
    mock_campaigns = [
        {
            "id": 1,
            "title": "Summer Swap Fest",
            "desc": "Flat 20% off on first 3 swaps",
            "status": "Active",
            "dates": "Mar 15 – Apr 15, 2026",
            "redemptions": "1,240",
            "revenue": "₹18,600",
        },
        {
            "id": 2,
            "title": "Weekend Warrior",
            "desc": "₹50 off every weekend swap",
            "status": "Active",
            "dates": "Mar 01 – Mar 31, 2026",
            "redemptions": "890",
            "revenue": "₹12,350",
        },
        {
            "id": 3,
            "title": "New User Welcome",
            "desc": "Free first swap for new users",
            "status": "Scheduled",
            "dates": "Apr 01 – Apr 30, 2026",
            "redemptions": "0",
            "revenue": "—",
        },
        {
            "id": 4,
            "title": "Winter Boost",
            "desc": "10% back on wallet recharges",
            "status": "Expired",
            "dates": "Dec 01 – Jan 31, 2026",
            "redemptions": "3,420",
            "revenue": "₹45,000",
        }
    ]
    return {"data": mock_campaigns, "total": len(mock_campaigns)}

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
    data: dict,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload a new document or a newer version of an existing document."""
    dealer = _get_dealer(db, current_user.id)
    from app.models.dealer import DealerDocument

    document_type = data.get("document_type", "other")
    category = data.get("category", "verification")
    file_url = data.get("file_url", "")
    valid_until_str = data.get("valid_until")

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

    data = []
    for r in rentals:
        customer = db.get(User, r.user_id)
        station = db.get(Station, r.start_station_id) if r.start_station_id else None
        data.append({
            "id": r.id,
            "transaction_type": "Rental",
            "amount": float(r.total_amount or 0),
            "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
            "created_at": str(r.created_at),
            "description": f"{customer.full_name if customer else 'Customer'} at {station.name if station else 'Station'}",
        })

    return {"data": data, "total": len(data)}
