from app.services.email_service import EmailService
from app.services.sms_service import SMSService
from app.services.fcm_service import FCMService
from app.models.user import User
from typing import List, Optional, Union

from app.models.notification import Notification
from sqlmodel import Session, select
from datetime import datetime

class NotificationService:
    @staticmethod
    def send_notification(
        db: Session,
        user: Union[User, int], 
        title: str, 
        message: str, 
        type: str = "info",
        channel: str = "push",
        payload: Optional[str] = None
    ):
        # --- Dealer Notification Preferences Check ---
        from app.models.dealer import DealerProfile
        from app.models.dealer_notification_pref import DealerNotificationPreference
        from datetime import datetime
        
        dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == user.id)).first()
        if dealer:
            pref = db.exec(select(DealerNotificationPreference).where(DealerNotificationPreference.dealer_id == dealer.id)).first()
            if pref:
                # 1. Check channel toggles
                if channel == "push" and not pref.push_notifications:
                    return
                if channel == "sms" and not pref.sms_notifications:
                    return
                
                # 2. Quiet Hours check
                if pref.quiet_hours_enabled and pref.quiet_hours and type != "critical":
                    try:
                        start_str = pref.quiet_hours.get("start", "22:00")
                        end_str = pref.quiet_hours.get("end", "07:00")
                        
                        now = datetime.now() # Local server time
                        current_minutes = now.hour * 60 + now.minute
                        
                        sh, sm = map(int, start_str.split(":"))
                        start_minutes = sh * 60 + sm
                        
                        eh, em = map(int, end_str.split(":"))
                        end_minutes = eh * 60 + em
                        
                        in_quiet_hours = False
                        if start_minutes < end_minutes:
                            in_quiet_hours = start_minutes <= current_minutes <= end_minutes
                        else: # Crosses midnight
                            in_quiet_hours = current_minutes >= start_minutes or current_minutes <= end_minutes
                            
                        if in_quiet_hours:
                            print(f"[Notifications] Suppressed '{title}' for dealer {dealer.id} due to quiet hours.")
                            return # Suppress notification
                    except Exception as e:
                        print(f"Quiet hours parsing error: {e}")
        # ---------------------------------------------
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
