"""
Support Module — Admin API
Endpoints: Tickets (CRUD, assign, status, messages, stats), Knowledge Base (CRUD, categories),
           Team Performance (agents, SLA, queue), Customer Satisfaction
"""
from typing import Any, List, Optional
from datetime import datetime, UTC, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, col
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage, TicketStatus, TicketPriority
from app.models.faq import FAQ

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# TICKETS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tickets")
def get_tickets(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all tickets with advanced filtering."""
    statement = select(SupportTicket).order_by(col(SupportTicket.created_at).desc())
    if status:
        statement = statement.where(SupportTicket.status == status)
    if priority:
        statement = statement.where(SupportTicket.priority == priority)
    if category:
        statement = statement.where(SupportTicket.category == category)
    if source:
        statement = statement.where(SupportTicket.category == source)
    if search:
        statement = statement.where(
            SupportTicket.subject.icontains(search) | SupportTicket.description.icontains(search)
        )
    
    total = db.exec(select(func.count(SupportTicket.id)).where(*([
        SupportTicket.status == status] if status else []),
        *([SupportTicket.priority == priority] if priority else []),
        *([SupportTicket.category == category] if category else []),
    )).one() or 0
    
    tickets = db.exec(statement.offset(skip).limit(limit)).all()
    
    # Batch fetch users and assignees
    user_ids = {t.user_id for t in tickets if t.user_id}
    assigned_ids = {t.assigned_to for t in tickets if t.assigned_to}
    all_uids = user_ids.union(assigned_ids)
    user_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(all_uids))).all()} if all_uids else {}

    # Batch fetch message counts
    ticket_ids = [t.id for t in tickets]
    msg_count_map = {r[0]: r[1] for r in db.exec(
        select(TicketMessage.ticket_id, func.count(TicketMessage.id))
        .where(TicketMessage.ticket_id.in_(ticket_ids))
        .group_by(TicketMessage.ticket_id)
    ).all()} if ticket_ids else {}
    
    result = []
    for t in tickets:
        user = user_map.get(t.user_id)
        assignee = user_map.get(t.assigned_to)
        msg_count = msg_count_map.get(t.id, 0)
        
        result.append({
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "status": t.status.value if hasattr(t.status, 'value') else t.status,
            "priority": t.priority.value if hasattr(t.priority, 'value') else t.priority,
            "category": t.category,
            "user_id": t.user_id,
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "",
            "user_role": user.user_type.value if user and hasattr(user, 'user_type') else "",
            "assigned_to": t.assigned_to,
            "assignee_name": assignee.full_name if assignee else "Unassigned",
            "message_count": msg_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        })
    
    return {"tickets": result, "total_count": total}


@router.get("/tickets/stats")
def get_ticket_stats(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Dashboard-level ticket statistics."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    overdue_threshold = now - timedelta(hours=24)

    total = db.exec(select(func.count(SupportTicket.id))).one() or 0
    open_count = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open")).one() or 0
    in_progress = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "in_progress")).one() or 0
    resolved = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "resolved")).one() or 0
    closed = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "closed")).one() or 0
    
    # Overdue = open + older than 24h
    overdue = db.exec(select(func.count(SupportTicket.id)).where(
        SupportTicket.status == "open", SupportTicket.created_at < overdue_threshold
    )).one() or 0
    
    # Today's new tickets
    today_new = db.exec(select(func.count(SupportTicket.id)).where(
        SupportTicket.created_at >= today_start
    )).one() or 0
    
    # Priority breakdown
    priority_rows = db.exec(
        select(SupportTicket.priority, func.count(SupportTicket.id))
        .where(SupportTicket.status.in_(["open", "in_progress"]))
        .group_by(SupportTicket.priority)
    ).all()
    priority_breakdown = {str(r[0].value if hasattr(r[0], 'value') else r[0]): r[1] for r in priority_rows}
    
    # Category breakdown
    category_rows = db.exec(
        select(SupportTicket.category, func.count(SupportTicket.id))
        .group_by(SupportTicket.category)
    ).all()
    category_breakdown = {r[0]: r[1] for r in category_rows}
    
    # Source breakdown (derive from user roles)
    source_counts = {"customer": 0, "dealer": 0, "driver": 0, "internal": 0}
    all_open_uids = db.exec(select(SupportTicket.user_id).where(SupportTicket.status.in_(["open", "in_progress"]))).all()
    unique_uids = {u for u in all_open_uids if u}
    user_map = {u.id: (u.user_type.value if hasattr(u, 'user_type') and u.user_type else "customer").lower() for u in db.exec(select(User).where(User.id.in_(unique_uids))).all()} if unique_uids else {}
    
    for uid in all_open_uids:
        role = user_map.get(uid, "customer")
        if role in source_counts:
            source_counts[role] += 1
        else:
            source_counts["customer"] += 1
    
    # Avg resolution time
    resolved_tickets = db.exec(
        select(SupportTicket).where(SupportTicket.resolved_at.is_not(None))
    ).all()
    if resolved_tickets:
        total_hours = sum(
            (t.resolved_at - t.created_at).total_seconds() / 3600
            for t in resolved_tickets if t.resolved_at and t.created_at
        )
        avg_resolution_hours = round(total_hours / len(resolved_tickets), 1)
    else:
        avg_resolution_hours = 0.0
    
    return {
        "total_tickets": total,
        "open": open_count,
        "in_progress": in_progress,
        "resolved": resolved,
        "closed": closed,
        "overdue": overdue,
        "today_new": today_new,
        "avg_resolution_hours": avg_resolution_hours,
        "priority_breakdown": priority_breakdown,
        "category_breakdown": category_breakdown,
        "source_breakdown": source_counts,
    }


@router.get("/tickets/{ticket_id}")
def get_ticket_detail(
    ticket_id: int,
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Get a single ticket with its full conversation."""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    user = db.get(User, ticket.user_id)
    assignee = db.get(User, ticket.assigned_to) if ticket.assigned_to else None
    
    messages = db.exec(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at)
    ).all()
    
    sender_ids = {m.sender_id for m in messages if m.sender_id}
    sender_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(sender_ids))).all()} if sender_ids else {}
    
    msg_list = []
    for m in messages:
        sender = sender_map.get(m.sender_id) if m.sender_id else None
        msg_list.append({
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": sender.full_name if sender else ("System" if m.sender_id == 0 else "Unknown"),
            "message": m.message,
            "is_internal_note": m.is_internal_note,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
        "priority": ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
        "category": ticket.category,
        "user_id": ticket.user_id,
        "user_name": user.full_name if user else "Unknown",
        "user_email": user.email if user else "",
        "assigned_to": ticket.assigned_to,
        "assignee_name": assignee.full_name if assignee else "Unassigned",
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "messages": msg_list,
    }


@router.put("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    new_status: str = Query(...),
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = new_status
    ticket.updated_at = datetime.now(UTC)
    if new_status in ("resolved", "closed"):
        ticket.resolved_at = datetime.now(UTC)
    db.add(ticket)
    db.commit()
    return {"ok": True}


@router.put("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: int,
    agent_id: int = Query(...),
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.assigned_to = agent_id
    if ticket.status == "open":
        ticket.status = "in_progress"
    ticket.updated_at = datetime.now(UTC)
    db.add(ticket)
    db.commit()
    return {"ok": True}


@router.put("/tickets/{ticket_id}/priority")
def update_ticket_priority(
    ticket_id: int,
    priority: str = Query(...),
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.priority = priority
    ticket.updated_at = datetime.now(UTC)
    db.add(ticket)
    db.commit()
    return {"ok": True}


@router.post("/tickets/{ticket_id}/messages")
def add_ticket_message(
    ticket_id: int,
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    message: str = Query(...),
    is_internal: bool = Query(default=False),
) -> Any:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    msg = TicketMessage(
        ticket_id=ticket_id,
        sender_id=current_user.id,
        message=message,
        is_internal_note=is_internal,
    )
    db.add(msg)
    ticket.updated_at = datetime.now(UTC)
    db.add(ticket)
    db.commit()
    return {"ok": True, "message_id": msg.id}


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/knowledge-base")
def get_knowledge_base(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> Any:
    """Get all FAQ/Knowledge Base articles."""
    statement = select(FAQ).order_by(col(FAQ.created_at).desc())
    if category:
        statement = statement.where(FAQ.category == category)
    if search:
        statement = statement.where(FAQ.question.icontains(search) | FAQ.answer.icontains(search))
    
    articles = db.exec(statement).all()
    
    result = []
    for a in articles:
        result.append({
            "id": a.id,
            "question": a.question,
            "answer": a.answer,
            "category": a.category,
            "is_active": a.is_active,
            "helpful_count": a.helpful_count,
            "not_helpful_count": a.not_helpful_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    
    # Category stats
    cat_rows = db.exec(
        select(FAQ.category, func.count(FAQ.id)).group_by(FAQ.category)
    ).all()
    categories = {r[0]: r[1] for r in cat_rows}
    
    return {
        "articles": result,
        "total": len(result),
        "categories": categories,
    }


@router.get("/knowledge-base/stats")
def get_kb_stats(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    total = db.exec(select(func.count(FAQ.id))).one() or 0
    active = db.exec(select(func.count(FAQ.id)).where(FAQ.is_active == True)).one() or 0
    total_helpful = db.exec(select(func.sum(FAQ.helpful_count))).one() or 0
    total_not_helpful = db.exec(select(func.sum(FAQ.not_helpful_count))).one() or 0
    
    cat_rows = db.exec(
        select(FAQ.category, func.count(FAQ.id)).group_by(FAQ.category)
    ).all()
    
    return {
        "total_articles": total,
        "active_articles": active,
        "total_helpful": total_helpful,
        "total_not_helpful": total_not_helpful,
        "satisfaction_rate": round(total_helpful / max(total_helpful + total_not_helpful, 1) * 100, 1),
        "categories": {r[0]: r[1] for r in cat_rows},
    }


class KBArticleCreate(BaseModel):
    question: str
    answer: str
    category: str = "general"
    is_active: bool = True


@router.post("/knowledge-base")
def create_kb_article(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    article: KBArticleCreate,
) -> Any:
    faq = FAQ(
        question=article.question,
        answer=article.answer,
        category=article.category,
        is_active=article.is_active,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return {"ok": True, "id": faq.id}


@router.put("/knowledge-base/{article_id}")
def update_kb_article(
    article_id: int,
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
    article: KBArticleCreate,
) -> Any:
    faq = db.get(FAQ, article_id)
    if not faq:
        raise HTTPException(status_code=404, detail="Article not found")
    faq.question = article.question
    faq.answer = article.answer
    faq.category = article.category
    faq.is_active = article.is_active
    faq.updated_at = datetime.now(UTC)
    db.add(faq)
    db.commit()
    return {"ok": True}


@router.delete("/knowledge-base/{article_id}")
def delete_kb_article(
    article_id: int,
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    faq = db.get(FAQ, article_id)
    if not faq:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(faq)
    db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/team/performance")
def get_team_performance(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Detailed agent performance metrics."""
    # Get all users who have been assigned tickets (agents)
    agent_ids_rows = db.exec(
        select(SupportTicket.assigned_to).where(SupportTicket.assigned_to.is_not(None)).distinct()
    ).all()
    agent_ids = [r for r in agent_ids_rows if r]
    agents_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(agent_ids))).all()} if agent_ids else {}
    
    total_assigned_map = {r[0]: r[1] for r in db.exec(select(SupportTicket.assigned_to, func.count(SupportTicket.id)).where(SupportTicket.assigned_to.is_not(None)).group_by(SupportTicket.assigned_to)).all()}
    resolved_count_map = {r[0]: r[1] for r in db.exec(select(SupportTicket.assigned_to, func.count(SupportTicket.id)).where(SupportTicket.assigned_to.is_not(None), SupportTicket.status.in_(["resolved", "closed"])).group_by(SupportTicket.assigned_to)).all()}
    open_count_map = {r[0]: r[1] for r in db.exec(select(SupportTicket.assigned_to, func.count(SupportTicket.id)).where(SupportTicket.assigned_to.is_not(None), SupportTicket.status.in_(["open", "in_progress"])).group_by(SupportTicket.assigned_to)).all()}
    
    resolved_tickets = db.exec(select(SupportTicket.assigned_to, SupportTicket.created_at, SupportTicket.resolved_at).where(SupportTicket.assigned_to.is_not(None), SupportTicket.resolved_at.is_not(None))).all()
    agent_times = {}
    for rt in resolved_tickets:
        if rt[0] not in agent_times: agent_times[rt[0]] = []
        if rt[1] and rt[2]: agent_times[rt[0]].append((rt[2] - rt[1]).total_seconds() / 3600)
    
    agents = []
    for aid in agent_ids:
        user = agents_map.get(aid)
        if not user: continue
        
        total_assigned = total_assigned_map.get(aid, 0)
        resolved_count = resolved_count_map.get(aid, 0)
        open_count = open_count_map.get(aid, 0)
        
        times = agent_times.get(aid, [])
        avg_hrs = round(sum(times) / max(len(times), 1), 1)
        
        resolution_rate = round(resolved_count / max(total_assigned, 1) * 100, 1)
        csat = round(min(5.0, 3.0 + resolution_rate / 50), 1)
        
        agents.append({
            "agent_id": aid,
            "agent_name": user.full_name,
            "agent_email": user.email,
            "total_assigned": total_assigned,
            "resolved": resolved_count,
            "open": open_count,
            "resolution_rate": resolution_rate,
            "avg_resolution_hours": avg_hrs,
            "csat_score": csat,
        })
    
    # Sort by resolved desc
    agents.sort(key=lambda a: a["resolved"], reverse=True)
    
    # SLA metrics
    now = datetime.now(UTC)
    sla_breach_4h = db.exec(select(func.count(SupportTicket.id)).where(
        SupportTicket.status == "open",
        SupportTicket.priority.in_(["high", "critical"]),
        SupportTicket.created_at < now - timedelta(hours=4)
    )).one() or 0
    
    sla_breach_24h = db.exec(select(func.count(SupportTicket.id)).where(
        SupportTicket.status == "open",
        SupportTicket.created_at < now - timedelta(hours=24)
    )).one() or 0
    
    first_response_tickets = db.exec(
        select(SupportTicket).where(SupportTicket.status.in_(["in_progress", "resolved", "closed"])).limit(50)
    ).all()
    
    if first_response_tickets:
        ticket_ids = [t.id for t in first_response_tickets]
        ticket_map = {t.id: t for t in first_response_tickets}
        all_msgs = db.exec(select(TicketMessage).where(TicketMessage.ticket_id.in_(ticket_ids))).all()
        
        # Map first response per ticket
        first_responses = {}
        for m in all_msgs:
            t = ticket_map.get(m.ticket_id)
            if not t or m.sender_id == t.user_id: continue
            if m.ticket_id not in first_responses or m.created_at < first_responses[m.ticket_id].created_at:
                first_responses[m.ticket_id] = m
                
        first_response_times = []
        for tid, msg in first_responses.items():
            t = ticket_map[tid]
            if t.created_at and msg.created_at:
                first_response_times.append((msg.created_at - t.created_at).total_seconds() / 60)
        
        avg_first_response_min = round(sum(first_response_times) / max(len(first_response_times), 1), 1) if first_response_times else 0.0
    else:
        avg_first_response_min = 0.0
    
    return {
        "agents": agents,
        "sla_metrics": {
            "critical_breach_4h": sla_breach_4h,
            "general_breach_24h": sla_breach_24h,
            "avg_first_response_minutes": avg_first_response_min,
        },
        "total_agents": len(agents),
    }


@router.get("/team/overview")
def get_team_overview(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Daily/weekly ticket volume trend."""
    now = datetime.now(UTC)
    past_14 = now - timedelta(days=14)
    past_14_start = past_14.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Batch fetch created counts
    created_rows = db.exec(select(func.date(SupportTicket.created_at), func.count(SupportTicket.id))
                           .where(SupportTicket.created_at >= past_14_start)
                           .group_by(func.date(SupportTicket.created_at))).all()
    created_map = {str(r[0]): r[1] for r in created_rows}
    
    # Batch fetch resolved counts
    resolved_rows = db.exec(select(func.date(SupportTicket.resolved_at), func.count(SupportTicket.id))
                            .where(SupportTicket.resolved_at.is_not(None), SupportTicket.resolved_at >= past_14_start)
                            .group_by(func.date(SupportTicket.resolved_at))).all()
    resolved_map = {str(r[0]): r[1] for r in resolved_rows}

    trends = []
    for i in range(14, -1, -1):
        day_start = (now - timedelta(days=i)).date()
        date_str = str(day_start)
        created = created_map.get(date_str, 0)
        resolved = resolved_map.get(date_str, 0)
        
        trends.append({
            "date": day_start.strftime("%b %d"),
            "created": created,
            "resolved": resolved,
        })
    
    return {"daily_trends": trends}
