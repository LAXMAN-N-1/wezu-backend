from __future__ import annotations
from typing import List, Optional
from sqlmodel import Session, select
from app.models.role_right import RoleRight
from app.schemas.role_right import RoleRightCreate, RoleRightUpdate

class RoleRightService:
    @staticmethod
    def create_or_update_role_right(db: Session, right_in: RoleRightCreate) -> RoleRight:
        # Check if already exists
        db_right = db.exec(
            select(RoleRight).where(
                RoleRight.role_id == right_in.role_id,
                RoleRight.menu_id == right_in.menu_id
            )
        ).first()

        if db_right:
            right_data = right_in.dict(exclude_unset=True)
            for key, value in right_data.items():
                setattr(db_right, key, value)
        else:
            db_right = RoleRight.from_orm(right_in)
        
        db.add(db_right)
        db.commit()
        db.refresh(db_right)
        return db_right

    @staticmethod
    def get_role_rights(db: Session, role_id: int) -> List[RoleRight]:
        return db.exec(select(RoleRight).where(RoleRight.role_id == role_id)).all()

    @staticmethod
    def get_role_right(db: Session, right_id: int) -> Optional[RoleRight]:
        return db.get(RoleRight, right_id)

    @staticmethod
    def update_role_right(db: Session, right_id: int, right_in: RoleRightUpdate) -> Optional[RoleRight]:
        db_right = db.get(RoleRight, right_id)
        if not db_right:
            return None
        right_data = right_in.dict(exclude_unset=True)
        for key, value in right_data.items():
            setattr(db_right, key, value)
        db.add(db_right)
        db.commit()
        db.refresh(db_right)
        return db_right

role_right_service = RoleRightService()
