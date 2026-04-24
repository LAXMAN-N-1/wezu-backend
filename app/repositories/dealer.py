from __future__ import annotations
from typing import Optional, List
from sqlmodel import Session, select
from app.repositories.base_repository import BaseRepository
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.dealer_inventory import DealerInventory
from app.models.dealer_promotion import DealerPromotion
from app.schemas.dealer import (
    DealerProfileCreate, DealerProfileUpdate,
    DealerApplicationUpdate,
    DealerInventoryAdjust,
    DealerPromotionCreate
)

class DealerProfileRepository(BaseRepository[DealerProfile, DealerProfileCreate, DealerProfileUpdate]):
    def __init__(self):
        super().__init__(model=DealerProfile)
    
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[DealerProfile]:
        return self.get_by_field(db, "user_id", user_id)

class DealerApplicationRepository(BaseRepository[DealerApplication, DealerApplication, DealerApplicationUpdate]):
    def __init__(self):
        super().__init__(model=DealerApplication)
        
    def get_by_dealer_id(self, db: Session, dealer_id: int) -> Optional[DealerApplication]:
        return self.get_by_field(db, "dealer_id", dealer_id)

class FieldVisitRepository(BaseRepository[FieldVisit, FieldVisit, FieldVisit]): # Schemas might need adjustment if used for Create/Update generics
    def __init__(self):
        super().__init__(model=FieldVisit)

class DealerInventoryRepository(BaseRepository[DealerInventory, DealerInventory, DealerInventoryAdjust]):
    def __init__(self):
        super().__init__(model=DealerInventory)

class DealerPromotionRepository(BaseRepository[DealerPromotion, DealerPromotionCreate, DealerPromotion]):
    def __init__(self):
        super().__init__(model=DealerPromotion)

dealer_profile_repository = DealerProfileRepository()
dealer_application_repository = DealerApplicationRepository()
field_visit_repository = FieldVisitRepository()
dealer_inventory_repository = DealerInventoryRepository()
dealer_promotion_repository = DealerPromotionRepository()
