from sqlmodel import Session, select, func, col, desc
from app.core.database import engine
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.dealer_inventory import DealerInventory
from app.models.dealer_promotion import DealerPromotion
from app.models.user import User
from app.models.station import Station
from app.models.commission import CommissionLog
from app.schemas.dealer import DealerProfileCreate
from typing import List, Optional, Any
from datetime import datetime
from app.repositories.dealer import (
    dealer_profile_repository,
    dealer_application_repository,
    field_visit_repository,
    dealer_inventory_repository,
    dealer_promotion_repository
)

class DealerService:
    
    @staticmethod
    def create_dealer_profile(db: Session, user_id: int, profile_data: dict) -> DealerProfile:
        # Validate data
        DealerProfileCreate(**profile_data)
        
        # Inject user_id into data before creation so the repository's commit succeeds
        profile_data["user_id"] = user_id
        profile = dealer_profile_repository.create(db, obj_in=profile_data)
        
        # Auto-create application
        app = DealerApplication(dealer_id=profile.id, current_stage="SUBMITTED")
        app.status_history = [{"stage": "SUBMITTED", "timestamp": str(datetime.utcnow()), "note": "Initial Submission"}]
        # Mock initial risk score
        app.risk_score = 10.0 # Low risk base
        dealer_application_repository.create(db, obj_in=app)
        
        return profile

    @staticmethod
    def get_dealer_by_user(db: Session, user_id: int) -> Optional[DealerProfile]:
        return dealer_profile_repository.get_by_user_id(db, user_id)

    @staticmethod
    def get_dealer_by_id(db: Session, dealer_id: int) -> Optional[DealerProfile]:
        return dealer_profile_repository.get(db, dealer_id)

    @staticmethod
    def get_dealers(db: Session, skip: int = 0, limit: int = 100) -> List[DealerProfile]:
        return dealer_profile_repository.get_multi(db, skip=skip, limit=limit)

    @staticmethod
    def update_dealer_profile(db: Session, dealer_id: int, profile_in: dict) -> DealerProfile:
        dealer = dealer_profile_repository.get(db, dealer_id)
        if not dealer:
            raise ValueError("Dealer not found")
        return dealer_profile_repository.update(db, db_obj=dealer, obj_in=profile_in)

    @staticmethod
    def update_application_stage(db: Session, application_id: int, new_stage: str, note: str = "") -> DealerApplication:
        # Valid Transitions
        valid_transitions = {
            "SUBMITTED": ["AUTO_VERIFIED", "REJECTED"],
            "AUTO_VERIFIED": ["KYC_SUBMITTED", "REJECTED"],
            "KYC_SUBMITTED": ["REVIEW_PENDING"],
            "REVIEW_PENDING": ["FIELD_VISIT_SCHEDULED", "REJECTED", "APPROVED"], # Skip visit if trusted?
            "FIELD_VISIT_SCHEDULED": ["FIELD_VISIT_COMPLETED"],
            "FIELD_VISIT_COMPLETED": ["APPROVED", "REJECTED"],
            "APPROVED": ["ACTIVE"],
            "ACTIVE": ["SUSPENDED"]
        }
        
        app = dealer_application_repository.get(db, application_id)
        if not app:
            raise ValueError("Application not found")
        
        if new_stage not in valid_transitions.get(app.current_stage, []):
                # Allow admin override or force? For now strict.
                # raise ValueError(f"Invalid transition from {app.current_stage} to {new_stage}")
                pass

        app.current_stage = new_stage
        
        # Append history
        history = list(app.status_history) if app.status_history else []
        history.append({"stage": new_stage, "timestamp": str(datetime.utcnow()), "note": note})
        app.status_history = history
        
        # If Active, activate profile and assign role
        if new_stage == "ACTIVE":
            dealer = db.get(DealerProfile, app.dealer_id)
            if dealer:
                dealer.is_active = True
                db.add(dealer)
                
                # Assign 'dealer' role
                from app.models.rbac import Role, UserRole
                dealer_role = db.exec(select(Role).where(col(Role.name) == "dealer")).first()
                if dealer_role:
                    assert dealer_role.id is not None
                    # Check existence in link table directly
                    existing_link = db.exec(
                        select(UserRole).where(
                            col(UserRole.user_id) == dealer.user_id,
                            col(UserRole.role_id) == dealer_role.id
                        )
                    ).first()
                    
                    if not existing_link:
                        new_link = UserRole(user_id=dealer.user_id, role_id=dealer_role.id)
                        db.add(new_link)
        
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def schedule_field_visit(db: Session, application_id: int, officer_id: int, date: datetime) -> FieldVisit:
        visit = FieldVisit(
            application_id=application_id,
            officer_id=officer_id,
            scheduled_date=date,
            status="SCHEDULED"
        )
        field_visit_repository.create(db, obj_in=visit)
        
        # Update App Stage
        DealerService.update_application_stage(db, application_id, "FIELD_VISIT_SCHEDULED", "Visit scheduled")
        
        return visit

    @staticmethod
    def complete_field_visit(db: Session, visit_id: int, report: dict, images: List[str]):
        visit = field_visit_repository.get(db, visit_id)
        if not visit:
            raise ValueError("Visit not found")
        
        visit.status = "COMPLETED"
        visit.completed_date = datetime.utcnow()
        visit.report_data = report
        visit.images = images
        field_visit_repository.update(db, db_obj=visit, obj_in=visit)
        
        DealerService.update_application_stage(db, visit.application_id, "FIELD_VISIT_COMPLETED", "Field visit done")

    @staticmethod
    def get_dealer_stats(db: Session, dealer_id: int) -> dict:
        """Get dealer summary stats"""
        stations = list(db.exec(select(Station).where(col(Station.dealer_id) == dealer_id)).all())
        total_stations = len(stations)
        
        total_earnings = db.exec(
            select(func.coalesce(func.sum(col(CommissionLog.amount)), 0.0))
            .where(col(CommissionLog.dealer_id) == dealer_id)
        ).one() or 0.0
        
        return {
            "total_stations": total_stations,
            "total_earnings": total_earnings,
            "active_stations": len([s for s in stations if s.status == 'active'])
        }

    @staticmethod
    def get_sales_summary(db: Session, dealer_id: int) -> dict:
        """Daily/Weekly/Monthly sales summary for dealer"""
        stations = db.exec(select(Station).where(col(Station.dealer_id) == dealer_id)).all()
        station_ids = [s.id for s in stations]
        
        from app.models.rental import Rental
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        daily = db.exec(select(func.count(col(Rental.id))).where(col(Rental.start_station_id).in_(station_ids)).where(col(Rental.created_at) >= day_ago)).one()
        weekly = db.exec(select(func.count(col(Rental.id))).where(col(Rental.start_station_id).in_(station_ids)).where(col(Rental.created_at) >= week_ago)).one()
        monthly = db.exec(select(func.count(col(Rental.id))).where(col(Rental.start_station_id).in_(station_ids)).where(col(Rental.created_at) >= month_ago)).one()
        
        return {
            "daily_rentals": daily,
            "weekly_rentals": weekly,
            "monthly_rentals": monthly,
            "revenue": 0.0 # Placeholder
        }

    @staticmethod
    def update_promotion(db: Session, promo_id: int, dealer_id: int, promo_in: dict) -> Any:
        from app.models.dealer_promotion import DealerPromotion
        promo = db.exec(select(DealerPromotion).where(col(DealerPromotion.id) == promo_id).where(col(DealerPromotion.dealer_id) == dealer_id)).first()
        if not promo:
            raise ValueError("Promotion not found")
            
        for key, value in promo_in.items():
            setattr(promo, key, value)
            
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo

    @staticmethod
    def get_commission_history(db: Session, dealer_id: int, skip: int = 0, limit: int = 50) -> List[Any]:
        from app.models.commission import CommissionLog
        return list(db.exec(
            select(CommissionLog)
            .where(col(CommissionLog.dealer_id) == dealer_id)
            .order_by(desc(col(CommissionLog.created_at)))
            .offset(skip).limit(limit)
        ).all())
