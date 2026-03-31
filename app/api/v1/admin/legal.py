from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.db.session import get_session
from app.models.user import User
from app.models.legal import LegalDocument
from app.schemas.legal import LegalDocumentCreate, LegalDocumentUpdate, LegalDocumentRead
from app.api.deps import get_current_active_admin
from datetime import datetime, UTC

router = APIRouter()

@router.get("/", response_model=List[LegalDocumentRead])
def read_legal_documents(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    query = select(LegalDocument)
    docs = session.exec(query).all()
    return docs

@router.post("/", response_model=LegalDocumentRead)
def create_legal_document(
    *,
    session: Session = Depends(get_session),
    doc_in: LegalDocumentCreate,
    admin: User = Depends(get_current_active_admin),
):
    db_doc = LegalDocument.model_validate(doc_in)
    db_doc.published_at = datetime.now(UTC)
    session.add(db_doc)
    session.commit()
    session.refresh(db_doc)
    return db_doc

@router.get("/{doc_id}", response_model=LegalDocumentRead)
def read_legal_document(
    doc_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    doc = session.get(LegalDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.patch("/{doc_id}", response_model=LegalDocumentRead)
def update_legal_document(
    *,
    session: Session = Depends(get_session),
    doc_id: int,
    doc_in: LegalDocumentUpdate,
    admin: User = Depends(get_current_active_admin),
):
    db_doc = session.get(LegalDocument, doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc_data = doc_in.model_dump(exclude_unset=True)
    for key, value in doc_data.items():
        setattr(db_doc, key, value)
    
    db_doc.updated_at = datetime.now(UTC)
    session.add(db_doc)
    session.commit()
    session.refresh(db_doc)
    return db_doc

@router.delete("/{doc_id}")
def delete_legal_document(
    doc_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    doc = session.get(LegalDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    session.delete(doc)
    session.commit()
    return {"ok": True}
