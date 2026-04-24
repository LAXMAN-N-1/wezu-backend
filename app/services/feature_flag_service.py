from __future__ import annotations
from sqlmodel import Session, select
from app.models.system import FeatureFlag
from typing import Optional
import random

class FeatureFlagService:
    @staticmethod
    def is_enabled(db: Session, name: str, user_id: Optional[int] = None, tenant_id: Optional[str] = None) -> bool:
        """
        Check if a feature flag is enabled for a specific context.
        """
        flag = db.exec(select(FeatureFlag).where(FeatureFlag.name == name)).first()
        if not flag or not flag.is_enabled:
            return False
            
        # Check rollout percentage
        if flag.rollout_percentage < 100:
            # Deterministic hash would be better, but simple random for now
            if random.randint(1, 100) > flag.rollout_percentage:
                return False
        
        # Check specific user/tenant targeting (JSON string parsing)
        if flag.enabled_for_tenants and tenant_id:
            import json
            tenants = json.loads(flag.enabled_for_tenants)
            if tenant_id not in tenants:
                return False
                
        return True
