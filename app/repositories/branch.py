from __future__ import annotations
from app.models.branch import Branch
from app.schemas.branch import BranchCreate, BranchUpdate
from app.repositories.base_repository import BaseRepository

class BranchRepository(BaseRepository[Branch, BranchCreate, BranchUpdate]):
    """Branch-specific data access methods"""
    
    def __init__(self):
        super().__init__(Branch)

# Singleton instance
branch_repository = BranchRepository()
