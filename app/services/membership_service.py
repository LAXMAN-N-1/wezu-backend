from sqlmodel import Session, select
from app.models.membership import UserMembership, MembershipTier
from datetime import datetime, timedelta
from typing import Dict, List, Any

class MembershipService:
    TIER_BENEFITS = {
        MembershipTier.BRONZE: [
            "Standard swap rates",
            "Email support"
        ],
        MembershipTier.SILVER: [
            "5% discount on swap rates",
            "Priority support",
            "Early access to new stations"
        ],
        MembershipTier.GOLD: [
            "10% discount on swap rates",
            "24/7 dedicated support",
            "Free spare battery delivery (1/month)",
            "Birthday rewards"
        ],
        MembershipTier.PLATINUM: [
            "15% discount on swap rates",
            "VIP concierge support",
            "Unlimited battery delivery",
            "Exclusive event invites"
        ]
    }

    @staticmethod
    def get_user_membership(db: Session, user_id: int) -> UserMembership:
        """Get or initialize user membership"""
        statement = select(UserMembership).where(UserMembership.user_id == user_id)
        membership = db.exec(statement).first()
        
        if not membership:
            membership = UserMembership(user_id=user_id)
            db.add(membership)
            db.commit()
            db.refresh(membership)
        
        return membership

    @staticmethod
    def get_tier_benefits(tier: MembershipTier) -> List[str]:
        return MembershipService.TIER_BENEFITS.get(tier, [])

    @staticmethod
    def check_upgrade_eligibility(membership: UserMembership) -> Dict[str, Any]:
        """Determine next tier and requirements"""
        tiers = list(MembershipTier)
        current_index = tiers.index(membership.tier)
        
        if current_index == len(tiers) - 1:
            return {"next_tier": None, "requirement": "Maximum tier reached"}
            
        next_tier = tiers[current_index + 1]
        
        # Simple points-based logic for MVP
        requirements = {
            MembershipTier.SILVER: 1000,
            MembershipTier.GOLD: 5000,
            MembershipTier.PLATINUM: 20000
        }
        
        req_points = requirements.get(next_tier, 0)
        points_needed = max(0, req_points - membership.points_balance)
        
        return {
            "next_tier": next_tier,
            "points_needed": points_needed,
            "progress_percentage": round(min(100, (membership.points_balance / req_points) * 100)) if req_points > 0 else 100
        }

    @staticmethod
    def earn_points(db: Session, user_id: int, amount: float, activity_type: str = "rental"):
        """Award loyalty points based on transaction amount"""
        membership = MembershipService.get_user_membership(db, user_id)
        
        # 1 point for every ₹10 spent
        points_earned = amount / 10.0
        membership.points_balance += points_earned
        membership.updated_at = datetime.utcnow()
        
        # 2. Check for tier promotion
        MembershipService._process_tier_promotion(membership)
        
        db.add(membership)
        db.commit()
        return points_earned

    @staticmethod
    def _process_tier_promotion(membership: UserMembership):
        """Automatically upgrade tier based on points balance"""
        requirements = {
            MembershipTier.SILVER: 1000,
            MembershipTier.GOLD: 5000,
            MembershipTier.PLATINUM: 20000
        }
        
        # Check from highest to lowest
        for tier in [MembershipTier.PLATINUM, MembershipTier.GOLD, MembershipTier.SILVER]:
            if membership.points_balance >= requirements[tier]:
                if membership.tier != tier:
                    membership.tier = tier
                    # Reset or extend expiry if logic exists
                    membership.tier_expiry = datetime.utcnow() + timedelta(days=365)
                break
