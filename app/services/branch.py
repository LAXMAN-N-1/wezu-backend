from __future__ import annotations
from sqlmodel import Session, select
from app.models.branch import Branch
from app.schemas.branch import BranchCreate, BranchUpdate
from app.repositories.branch import branch_repository
from typing import List, Optional

class BranchService:
    @staticmethod
    def get_branches(db: Session, skip: int = 0, limit: int = 100) -> List[Branch]:
        return branch_repository.get_multi(db, skip=skip, limit=limit)

    @staticmethod
    def get_branch_by_id(db: Session, branch_id: int) -> Optional[Branch]:
        return branch_repository.get(db, branch_id)

    @staticmethod
    def get_branch_by_code(db: Session, code: str) -> Optional[Branch]:
        return branch_repository.get_by_field(db, "code", code)

    @staticmethod
    def create_branch(db: Session, branch_in: BranchCreate) -> Branch:
        return branch_repository.create(db, obj_in=branch_in)

    @staticmethod
    def update_branch(db: Session, branch_id: int, branch_in: BranchUpdate) -> Optional[Branch]:
        db_obj = branch_repository.get(db, branch_id)
        if not db_obj:
            return None
        return branch_repository.update(db, db_obj=db_obj, obj_in=branch_in)

    @staticmethod
    def delete_branch(db: Session, branch_id: int) -> Optional[Branch]:
        if not branch_repository.exists(db, branch_id):
            return None
        return branch_repository.delete(db, id=branch_id)

branch_service = BranchService()
