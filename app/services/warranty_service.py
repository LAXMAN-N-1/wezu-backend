from sqlmodel import Session, select
from fastapi import HTTPException
from datetime import datetime, timedelta
import uuid
from typing import Optional, List

from app.models.warranty_claim import WarrantyClaim, ClaimStatus
from app.schemas.warranty import WarrantyClaimCreate, WarrantyClaimUpdate, WarrantyCheckResponse
from app.models.catalog import CatalogOrder
from app.models.user import User
from app.services.notification_service import NotificationService

class WarrantyService:
    @staticmethod
    def check_eligibility(db: Session, order_id: int) -> WarrantyCheckResponse:
        order = db.get(CatalogOrder, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        # Look for battery items in the order
        battery_items = [item for item in order.items if item.warranty_months > 0]
        if not battery_items:
            return WarrantyCheckResponse(
                order_id=order_id,
                is_eligible=False,
                reason="No applicable warranty found for items in this order."
            )
            
        start_date = order.delivered_at or order.created_at
        
        # Base overall eligibility on the max warranty item for simplicity
        max_warranty_months = max(item.warranty_months for item in battery_items)
        warranty_end = start_date + timedelta(days=max_warranty_months * 30)
        
        days_remaining = (warranty_end - datetime.utcnow()).days
        
        if days_remaining >= 0:
            return WarrantyCheckResponse(
                order_id=order_id,
                is_eligible=True,
                reason="Order is within warranty period.",
                days_remaining=days_remaining
            )
        else:
            return WarrantyCheckResponse(
                order_id=order_id,
                is_eligible=False,
                reason="Warranty has expired.",
                days_remaining=0
            )

    @staticmethod
    def create_claim(db: Session, user_id: int, claim_data: WarrantyClaimCreate) -> WarrantyClaim:
        eligibility = WarrantyService.check_eligibility(db, claim_data.order_id)
        if not eligibility.is_eligible:
            raise HTTPException(status_code=400, detail=f"Cannot submit claim: {eligibility.reason}")
            
        new_claim = WarrantyClaim(
            user_id=user_id,
            order_id=claim_data.order_id,
            product_id=claim_data.product_id,
            claim_type=claim_data.claim_type,
            description=claim_data.description,
            photos=claim_data.photos,
            status=ClaimStatus.SUBMITTED
        )
        db.add(new_claim)
        db.commit()
        db.refresh(new_claim)
        
        user = db.get(User, user_id)
        if user:
            NotificationService.send_notification(
                db=db,
                user=user,
                title="Warranty Claim Submitted",
                message=f"We have received your warranty claim. It is currently under review.",
                channel="email"
            )
            
        return new_claim

    @staticmethod
    def update_claim_status(db: Session, claim_id: uuid.UUID, admin_id: int, status_data: WarrantyClaimUpdate) -> WarrantyClaim:
        claim = db.get(WarrantyClaim, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Warranty claim not found")
            
        if claim.status in [ClaimStatus.RESOLVED]:
            raise HTTPException(status_code=400, detail="Cannot alter a resolved claim.")
            
        claim.status = status_data.status
        claim.updated_at = datetime.utcnow()
        
        if status_data.admin_notes:
            claim.admin_notes = status_data.admin_notes
        if status_data.resolution:
            claim.resolution = status_data.resolution
            
        db.add(claim)
        db.commit()
        db.refresh(claim)
        
        user = db.get(User, claim.user_id)
        if user:
            NotificationService.send_notification(
                db=db,
                user=user,
                title=f"Warranty Claim Update: {claim.status.value.upper()}",
                message=f"Your claim status has been updated to {claim.status.value}. Notes: {claim.resolution or 'No additional notes provided.'}",
                channel="email"
            )
            
        return claim
    
    @staticmethod
    def get_user_claims(db: Session, user_id: int, status: Optional[ClaimStatus] = None) -> List[WarrantyClaim]:
        query = select(WarrantyClaim).where(WarrantyClaim.user_id == user_id)
        if status:
            query = query.where(WarrantyClaim.status == status)
        query = query.order_by(WarrantyClaim.created_at.desc())
        return db.exec(query).all()

    @staticmethod
    def get_all_claims(db: Session, status: Optional[ClaimStatus] = None) -> List[WarrantyClaim]:
        query = select(WarrantyClaim)
        if status:
            query = query.where(WarrantyClaim.status == status)
        query = query.order_by(WarrantyClaim.created_at.desc())
        return db.exec(query).all()
