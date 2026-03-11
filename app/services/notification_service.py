from app.services.email_service import EmailService
from app.services.sms_service import SMSService
from app.services.fcm_service import FCMService
from app.models.user import User
from typing import List, Optional

from app.models.notification import Notification
from sqlmodel import Session, select
from datetime import datetime

class NotificationService:
    @staticmethod
    def send_notification(
        db: Session,
        user: User, 
        title: str, 
        message: str, 
        type: str = "info",
        channel: str = "push",
        payload: Optional[str] = None
    ):
        # 1. Save to DB
        notif = Notification(
            user_id=user.id,
            title=title,
            message=message,
            type=type,
            channel=channel,
            payload=payload,
            status="sent" # Assume success for now
        )
        db.add(notif)
        db.commit() # Save history
        
        # 2. Dispatch
        if channel == "push":
            # Lazy load devices
            from app.models.device import Device
            devices = db.exec(select(Device).where(Device.user_id == user.id)).all()
            tokens = [d.fcm_token for d in devices if d.fcm_token]
            if tokens:
                FCMService.send_multicast(tokens, title, message, data={"type": type, "payload": payload})
        
        elif channel == "email" and user.email:
            EmailService.send_email(user.email, title, message)
            
        elif channel == "sms" and user.phone_number:
            SMSService.send_sms(user.phone_number, message)
            
        elif channel == "whatsapp":
             # Mock WhatsApp
             pass

    @staticmethod
    def schedule_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        scheduled_at: datetime,
        channel: str = "push"
    ):
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type="info",
            channel=channel,
            scheduled_at=scheduled_at,
            status="pending"
        )
        db.add(notif)
        db.commit()
        return notif
    @staticmethod
    def get_user_notifications(db: Session, user_id: int) -> List[Notification]:
        return db.exec(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())).all()

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int):
        notif = db.get(Notification, notification_id)
        if notif and notif.user_id == user_id:
            notif.is_read = True
            db.add(notif)
            db.commit()

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        statement = select(Notification).where(Notification.user_id == user_id, Notification.is_read == False)
        unread = db.exec(statement).all()
        for notif in unread:
            notif.is_read = True
            db.add(notif)
        db.commit()
        return len(unread)

    @staticmethod
    def clear_all_notifications(db: Session, user_id: int) -> int:
        statement = select(Notification).where(Notification.user_id == user_id)
        notifications = db.exec(statement).all()
        for notif in notifications:
            db.delete(notif)
        db.commit()
        return len(notifications)

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        from sqlmodel import func
        statement = select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read == False)
        return db.exec(statement).one()

    @staticmethod
    def send_bulk_notification(
        db: Session,
        segment: str,
        title: str,
        message: str,
        type: str = "info",
        channel: str = "push"
    ) -> int:
        from app.models.user import User
        statement = select(User).where(User.is_active == True)
        
        if segment == "dealers":
             from app.models.dealer import DealerProfile
             statement = statement.join(DealerProfile, User.id == DealerProfile.user_id)
        elif segment == "drivers":
             from app.models.driver_profile import DriverProfile
             statement = statement.join(DriverProfile, User.id == DriverProfile.user_id)
        
        users = db.exec(statement).all()
        for user in users:
            NotificationService.send_notification(db, user, title, message, type, channel)
            
        return len(users)
