from typing import List, Optional
from sqlmodel import Session, select
from app.models.rbac import Role
from app.schemas.role import RoleCreate, RoleUpdate

class RoleService:
    @staticmethod
    def create_role(db: Session, role_in: RoleCreate) -> Role:
        db_role = Role(name=role_in.name, description=role_in.description) # Explicit mapping for safety
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def get_role(db: Session, role_id: int) -> Optional[Role]:
        return db.get(Role, role_id)

    @staticmethod
    def get_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
        return db.exec(select(Role).offset(skip).limit(limit)).all()

    @staticmethod
    def update_role(db: Session, role_id: int, role_in: RoleUpdate) -> Optional[Role]:
        db_role = db.get(Role, role_id)
        if not db_role:
            return None
        role_data = role_in.dict(exclude_unset=True)
        for key, value in role_data.items():
            setattr(db_role, key, value)
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def delete_role(db: Session, role_id: int) -> bool:
        db_role = db.get(Role, role_id)
        if not db_role:
            return False
        db.delete(db_role)
        db.commit()
        return True

role_service = RoleService()
