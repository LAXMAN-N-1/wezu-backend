from sqlmodel import Session, select
from typing import List, Optional
from app.models.grn import GRN, GRNItem

class GRNRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def create_grn(self, grn: GRN) -> GRN:
        self.session.add(grn)
        self.session.commit()
        self.session.refresh(grn)
        return grn
        
    def get_by_id(self, grn_id: int) -> Optional[GRN]:
        return self.session.get(GRN, grn_id)
        
    def get_by_indent(self, indent_id: int) -> List[GRN]:
        statement = select(GRN).where(GRN.indent_id == indent_id).order_by(GRN.created_at.desc())
        return self.session.exec(statement).all()

    def update(self, grn: GRN) -> GRN:
        self.session.add(grn)
        self.session.commit()
        self.session.refresh(grn)
        return grn
