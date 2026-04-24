from __future__ import annotations
from sqlmodel import Session, select
from typing import TypeVar, Generic, Type, Optional, List, Any

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[T]:
        return db.get(self.model, id)

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[T]:
        statement = select(self.model).offset(skip).limit(limit)
        return db.exec(statement).all()

    def create(self, db: Session, obj_in: dict) -> T:
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: T, obj_in: dict) -> T:
        for key, value in obj_in.items():
            setattr(db_obj, key, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: Any) -> Optional[T]:
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
