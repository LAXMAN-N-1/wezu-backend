"""
Dealer Portal Dashboard — Aggregated KPIs, alerts, and activity feed.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from datetime import datetime, timedelta

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station
from app.models.dealer_inventory import DealerInventory
from app.models.support import SupportTicket, TicketStatus
from app.models.notification import Notification

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
        from app.models.rental import Rental
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
        now = datetime.utcnow()
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

    return {"activities": activities, "total": len(activities)}
