from __future__ import annotations
"""
Enhanced Support Endpoints
Additional support operations including attachments and FAQ search
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.models.support import SupportTicket
from app.models.faq import FAQ
from app.db.session import get_session
from pydantic import BaseModel
import os
import shutil

router = APIRouter()


@router.post("/tickets/{ticket_id}/attachment")
def upload_ticket_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Upload attachment to support ticket"""
    # Get ticket
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Save file
    os.makedirs("uploads/support", exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"ticket_{ticket_id}_{file.filename}"
    file_path = f"uploads/support/{file_name}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "message": "Attachment uploaded successfully",
        "file_path": f"/{file_path}",
        "file_name": file.filename
    }


@router.get("/faq/search")
def search_faq(
    q: str,
    db: Session = Depends(get_session)
):
    """Search FAQ by keyword"""
    from sqlmodel import select
    
    statement = select(FAQ).where(
        (FAQ.question.contains(q)) |
        (FAQ.answer.contains(q))
    )
    results = db.exec(statement).all()
    
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }
