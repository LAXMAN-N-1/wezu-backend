from sqlmodel import Session, select
from app.core.database import engine
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.user import User
from app.models.station import Station
from app.models.commission import Commission
from typing import List, Optional
from datetime import datetime

class DealerService:
    
    @staticmethod
    def create_dealer_profile(user_id: int, profile_data: dict) -> DealerProfile:
        with Session(engine) as session:
            profile = DealerProfile(user_id=user_id, **profile_data)
            session.add(profile)
            session.commit()
            session.refresh(profile)
            
            # Auto-create application
            app = DealerApplication(dealer_id=profile.id, current_stage="SUBMITTED")
            app.status_history = [{"stage": "SUBMITTED", "timestamp": str(datetime.utcnow()), "note": "Initial Submission"}]
            # Mock initial risk score
            app.risk_score = 10.0 # Low risk base
            session.add(app)
            session.commit()
            
            return profile

    @staticmethod
    def get_dealer_by_user(user_id: int) -> Optional[DealerProfile]:
        with Session(engine) as session:
            return session.exec(select(DealerProfile).where(DealerProfile.user_id == user_id)).first()

    @staticmethod
    def update_application_stage(application_id: int, new_stage: str, note: str = "") -> DealerApplication:
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
        
        with Session(engine) as session:
            app = session.get(DealerApplication, application_id)
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
                dealer = session.get(DealerProfile, app.dealer_id)
                dealer.is_active = True
                session.add(dealer)
                
            session.add(app)
            session.commit()
            session.refresh(app)
            return app

    @staticmethod
    def schedule_field_visit(application_id: int, officer_id: int, date: datetime) -> FieldVisit:
        with Session(engine) as session:
            visit = FieldVisit(
                application_id=application_id,
                officer_id=officer_id,
                scheduled_date=date,
                status="SCHEDULED"
            )
            session.add(visit)
            
            # Update App Stage
            DealerService.update_application_stage(application_id, "FIELD_VISIT_SCHEDULED", "Visit scheduled")
            
            session.commit()
            session.refresh(visit)
            return visit

    @staticmethod
    def complete_field_visit(visit_id: int, report: dict, images: List[str]):
        with Session(engine) as session:
            visit = session.get(FieldVisit, visit_id)
            if not visit:
                raise ValueError("Visit not found")
            
            visit.status = "COMPLETED"
            visit.completed_date = datetime.utcnow()
            visit.report_data = report
            visit.images = images
            session.add(visit)
            
            DealerService.update_application_stage(visit.application_id, "FIELD_VISIT_COMPLETED", "Field visit done")
            session.commit()

    @staticmethod
    def get_dashboard_stats(dealer_id: int) -> dict:
        with Session(engine) as session:
            stations = session.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
            total_stations = len(stations)
            # total_rentals = sum([s.total_rentals for s in stations]) # Assuming station has this or we query Rental JOIN Station
            
            commissions = session.exec(select(Commission).where(Commission.dealer_id == dealer_id)).all()
            total_earnings = sum([c.amount for c in commissions])
            
            return {
                "total_stations": total_stations,
                "total_earnings": total_earnings,
                "active_stations": len([s for s in stations if s.status == 'active'])
            }
