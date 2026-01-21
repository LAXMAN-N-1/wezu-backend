from sqlmodel import Session, select
from app.core.database import engine
from app.models.video_kyc import VideoKYCSession
from app.models.user import User
from datetime import datetime
import uuid

class VideoKYCService:
    @staticmethod
    def schedule_session(user_id: int, scheduled_time: datetime) -> VideoKYCSession:
        with Session(engine) as session:
            # Check existing pending
            existing = session.exec(select(VideoKYCSession).where(
                VideoKYCSession.user_id == user_id, 
                VideoKYCSession.status.in_(["initiated", "scheduled"])
            )).first()
            if existing:
                existing.scheduled_at = scheduled_time
                existing.status = "scheduled"
                session.add(existing)
                session.commit()
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
            session.commit()
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
    def update_status(session_id: int, status: str, recording_url: str = None):
        with Session(engine) as session:
            vks = session.get(VideoKYCSession, session_id)
            if vks:
                 vks.status = status
                 if status == "completed":
                     vks.completed_at = datetime.utcnow()
                 if recording_url:
                     vks.video_url = recording_url
                 session.add(vks)
                 session.commit()
