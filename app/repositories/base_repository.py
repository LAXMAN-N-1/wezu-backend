from __future__ import annotations
"""
Base Repository Pattern
Provides generic CRUD operations for all models
"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Union
from sqlmodel import Session, select, func
from sqlalchemy import desc, asc
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository with generic CRUD operations
    """
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Get a single record by ID"""
        return db.get(self.model, id)
    
    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[ModelType]:
        """Get multiple records with pagination"""
        query = select(self.model).offset(skip).limit(limit)
        
        if order_by:
            order_column = getattr(self.model, order_by, None)
            if order_column is not None:
                if order_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
        
        return list(db.exec(query).all())
    
    def get_by_field(
        self,
        db: Session,
        field: str,
        value: Any
    ) -> Optional[ModelType]:
        """Get a single record by field value"""
        query = select(self.model).where(getattr(self.model, field) == value)
        return db.exec(query).first()
    
    def get_multi_by_field(
        self,
        db: Session,
        field: str,
        value: Any,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records by field value"""
        query = select(self.model).where(
            getattr(self.model, field) == value
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record"""
        obj_in_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update an existing record"""
        obj_data = db_obj.dict() if hasattr(db_obj, 'dict') else {}
        
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: int) -> ModelType:
        """Delete a record"""
        obj = db.get(self.model, id)
        db.delete(obj)
        db.commit()
        return obj
    
    def count(self, db: Session) -> int:
        """Count total records"""
        return db.exec(select(func.count()).select_from(self.model)).one()
    
    def exists(self, db: Session, id: int) -> bool:
        """Check if record exists"""
        return db.get(self.model, id) is not None
    
    def filter(
        self,
        db: Session,
        *,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Filter records by multiple fields"""
        query = select(self.model)
        
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        
        query = query.offset(skip).limit(limit)
        return list(db.exec(query).all())
