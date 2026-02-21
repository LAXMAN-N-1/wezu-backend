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
        return db.exec(
            select(Review)
            .where(Review.station_id == station_id, Review.is_hidden == False)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()

    @staticmethod
    def update_review(db: Session, review_id: int, user_id: int, review_in: dict) -> Review:
        review = db.get(Review, review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        if review.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to edit this review")
        
        for field, value in review_in.items():
            setattr(review, field, value)
            
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    @staticmethod
    def delete_review(db: Session, review_id: int, user_id: int, is_admin: bool = False) -> bool:
        review = db.get(Review, review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        if not is_admin and review.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this review")
        
        db.delete(review)
        db.commit()
        return True

    @staticmethod
    def list_reviews_admin(db: Session, skip: int = 0, limit: int = 100) -> List[Review]:
        return db.exec(select(Review).order_by(Review.created_at.desc()).offset(skip).limit(limit)).all()

    @staticmethod
    def toggle_review_visibility(db: Session, review_id: int, is_hidden: bool) -> Review:
        review = db.get(Review, review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        review.is_hidden = is_hidden
        db.add(review)
        db.commit()
        db.refresh(review)
        return review
