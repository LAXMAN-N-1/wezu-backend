from sqlmodel import Session, select
from app.models.review import Review
from app.schemas.review import ReviewCreate
from typing import List

class ReviewService:
    @staticmethod
    def create_review(db: Session, user_id: int, review_in: ReviewCreate) -> Review:
        review = Review(**review_in.dict(), user_id=user_id)
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    @staticmethod
    def get_by_station(db: Session, station_id: int, skip: int = 0, limit: int = 50) -> List[Review]:
        return db.exec(select(Review).where(Review.station_id == station_id).offset(skip).limit(limit)).all()
