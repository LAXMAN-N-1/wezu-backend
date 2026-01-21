"""
Notification Repository
Data access layer for Notification model
"""
from typing import List
from sqlmodel import Session, select
from app.models.notification import Notification
from app.repositories.base_repository import BaseRepository
from pydantic import BaseModel


class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str
    type: str
    channel: str = "push"


class NotificationUpdate(BaseModel):
    is_read: bool = True


class NotificationRepository(BaseRepository[Notification, NotificationCreate, NotificationUpdate]):
    """Notification-specific data access methods"""
    
    def __init__(self):
        super().__init__(Notification)
    
    def get_user_notifications(
        self,
        db: Session,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Notification]:
        """Get all notifications for a user"""
        query = select(Notification).where(
            Notification.user_id == user_id
        ).order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def get_unread_notifications(
        self,
        db: Session,
        user_id: int,
        *,
        limit: int = 100
    ) -> List[Notification]:
        """Get unread notifications for a user"""
        query = select(Notification).where(
            (Notification.user_id == user_id) &
            (Notification.is_read == False)
        ).order_by(Notification.created_at.desc()).limit(limit)
        return list(db.exec(query).all())
    
    def mark_as_read(self, db: Session, notification_id: int) -> Notification:
        """Mark notification as read"""
        notification = self.get(db, notification_id)
        if notification:
            notification.is_read = True
            db.add(notification)
            db.commit()
            db.refresh(notification)
        return notification
    
    def mark_all_as_read(self, db: Session, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        notifications = self.get_unread_notifications(db, user_id)
        count = 0
        for notification in notifications:
            notification.is_read = True
            db.add(notification)
            count += 1
        db.commit()
        return count


# Singleton instance
notification_repository = NotificationRepository()
