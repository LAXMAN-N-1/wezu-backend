from sqlmodel import Session, select
from app.core.database import engine
from app.models.video_kyc import VideoKYCSession
from app.models.user import User
from datetime import datetime, UTC
import uuid

class VideoKYCService:
    @staticmethod
    def schedule_session(user_id: int, scheduled_time: datetime, db: Session = None) -> VideoKYCSession:
        if db:
            return VideoKYCService._schedule_session_impl(db, user_id, scheduled_time, commit=False)
        with Session(engine) as session:
            return VideoKYCService._schedule_session_impl(session, user_id, scheduled_time, commit=True)
            
    @staticmethod
    def _schedule_session_impl(session: Session, user_id: int, scheduled_time: datetime, commit: bool = True) -> VideoKYCSession:
        # Check existing pending
        existing = session.exec(select(VideoKYCSession).where(
            VideoKYCSession.user_id == user_id, 
            VideoKYCSession.status.in_(["initiated", "scheduled"])
        )).first()
        if existing:
            existing.scheduled_at = scheduled_time
            existing.status = "scheduled"
            session.add(existing)
            if commit:
                session.commit()
                session.refresh(existing)
            else:
                session.flush() # Ensure ID is available if needed
                session.refresh(existing)
            return existing
        
        session_id = str(uuid.uuid4())
        vks = VideoKYCSession(
            user_id=user_id,
            session_id=session_id,
            status="scheduled",
            scheduled_at=scheduled_time,
            provider="internal" # or Agora/Twilio
        )
        session.add(vks)
        if commit:
            session.commit()
            session.refresh(vks)
        else:
             session.flush()
             session.refresh(vks)
        return vks

    @staticmethod
    def assign_agent(session_id: int, agent_id: int) -> VideoKYCSession:
        with Session(engine) as session:
            vks = session.get(VideoKYCSession, session_id)
            if not vks:
                raise ValueError("Session not found")
            vks.agent_id = agent_id
            session.add(vks)
            session.commit()
            session.refresh(vks)
            return vks

    @staticmethod
    def update_status(session_id: int, status: str, recording_url: str = None, notes: str = None, db: Session = None):
        if db:
             return VideoKYCService._update_status_impl(db, session_id, status, recording_url, notes, commit=False)
        with Session(engine) as session:
             return VideoKYCService._update_status_impl(session, session_id, status, recording_url, notes, commit=True)

    @staticmethod
    def _update_status_impl(session: Session, session_id: int, status: str, recording_url: str = None, notes: str = None, commit: bool = True):
        vks = session.get(VideoKYCSession, session_id)
        if vks:
                vks.status = status
                if status == "completed":
                    vks.completed_at = datetime.now(UTC)
                if recording_url:
                    vks.video_url = recording_url
                if notes:
                    vks.agent_notes = notes
                session.add(vks)
                if commit:
                    session.commit()
                    session.refresh(vks)
                else:
                    session.flush()
                    session.refresh(vks)
        return vks
