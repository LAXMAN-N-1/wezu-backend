from sqlmodel import Session, select
from typing import List, Optional
from app.models.indent import Indent, IndentItem

class IndentRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def create_indent(self, indent: Indent) -> Indent:
        self.session.add(indent)
        self.session.commit()
        self.session.refresh(indent)
        return indent
        
    def get_by_id(self, indent_id: int) -> Optional[Indent]:
        return self.session.get(Indent, indent_id)
        
    def get_by_dealer(self, dealer_id: int) -> List[Indent]:
        statement = select(Indent).where(Indent.dealer_id == dealer_id).order_by(Indent.created_at.desc())
        return self.session.exec(statement).all()
        
    def get_by_warehouse(self, warehouse_id: int) -> List[Indent]:
        statement = select(Indent).where(Indent.warehouse_id == warehouse_id).order_by(Indent.created_at.desc())
        return self.session.exec(statement).all()

    def update(self, indent: Indent) -> Indent:
        self.session.add(indent)
        self.session.commit()
        self.session.refresh(indent)
        return indent
