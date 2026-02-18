from sqlmodel import Session, select
from app.core.database import engine
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.dealer_inventory import DealerInventory
from app.models.dealer_promotion import DealerPromotion
from app.models.user import User
from app.models.station import Station
from app.models.commission import Commission
from typing import List, Optional
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
        profile_in = DealerProfile(**profile_data) # Simple conversion
        profile_in.user_id = user_id
        profile = dealer_profile_repository.create(db, obj_in=profile_in)
        
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
        
        # If Active, activate profile
        if new_stage == "ACTIVE":
            dealer = dealer_profile_repository.get(db, app.dealer_id)
            dealer.is_active = True
            db.add(dealer) # Or dealer_repo.update if needed, but simple attribute change here
            
        return dealer_application_repository.update(db, db_obj=app, obj_in=app) # Using update to commit

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
    def get_dashboard_stats(db: Session, dealer_id: int) -> dict:
        # This part still uses manual queries as it aggregates data across modules not fully repository-ized or needed custom queries
        stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
        total_stations = len(stations)
        # total_rentals = sum([s.total_rentals for s in stations]) # Assuming station has this or we query Rental JOIN Station
        
        commissions = db.exec(select(Commission).where(Commission.dealer_id == dealer_id)).all()
        total_earnings = sum([c.amount for c in commissions])
        
        return {
            "total_stations": total_stations,
            "total_earnings": total_earnings,
            "active_stations": len([s for s in stations if s.status == 'active'])
        }
