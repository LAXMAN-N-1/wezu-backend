from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlmodel import Session, select
from typing import Any, List
from datetime import datetime

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile, DealerDocument

router = APIRouter()

def _get_dealer_id(db: Session, user_id: int) -> int:
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    return dealer.id

@router.get("")
def list_documents(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all documents for the dealer, returning only the active version of each type."""
    dealer_id = _get_dealer_id(db, current_user.id)
    
    # Simple explicit map: get all docs, group by document_type, take max version
    docs = db.exec(
        select(DealerDocument)
        .where(DealerDocument.dealer_id == dealer_id)
        .where(DealerDocument.status != "ARCHIVED")
    ).all()
    
    # We want latest versions
    latest_docs = {}
    for d in docs:
        if d.document_type not in latest_docs or d.version > latest_docs[d.document_type].version:
            latest_docs[d.document_type] = d
            
    return list(latest_docs.values())

@router.get("/{document_type}/history")
def get_document_history(
    document_type: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get all versions of a specific document type."""
    dealer_id = _get_dealer_id(db, current_user.id)
    docs = db.exec(
        select(DealerDocument)
        .where(DealerDocument.dealer_id == dealer_id)
        .where(DealerDocument.document_type == document_type)
        .order_by(DealerDocument.version.desc())
    ).all()
    return docs

@router.post("/upload")
def upload_document_version(
    document_type: str = Body(...),
    category: str = Body("verification"),
    file_url: str = Body(...), # Or realistically passing an UploadFile via form and storing to S3
    valid_until: datetime = Body(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload a new document or a newer version of an existing document."""
    dealer_id = _get_dealer_id(db, current_user.id)
    
    # Check if existing document
    existing_docs = db.exec(
        select(DealerDocument)
        .where(DealerDocument.dealer_id == dealer_id)
        .where(DealerDocument.document_type == document_type)
    ).all()
    
    next_version = 1
    if existing_docs:
        # Archive all existing
        for doc in existing_docs:
            if doc.status != "ARCHIVED":
                doc.status = "ARCHIVED"
        
        highest = max(d.version for d in existing_docs)
        next_version = highest + 1

    new_doc = DealerDocument(
        dealer_id=dealer_id,
        document_type=document_type,
        category=category,
        file_url=file_url,
        version=next_version,
        status="PENDING",
        valid_until=valid_until,
        is_verified=False
    )
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return {"message": "Document uploaded successfully", "document": new_doc}

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Soft delete / archive a document."""
    dealer_id = _get_dealer_id(db, current_user.id)
    doc = db.get(DealerDocument, document_id)
    if not doc or doc.dealer_id != dealer_id:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc.status = "ARCHIVED"
    db.commit()
    return {"message": "Document archived"}
