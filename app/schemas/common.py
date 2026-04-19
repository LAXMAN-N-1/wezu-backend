from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Generic, TypeVar, List, Any

T = TypeVar('T')

class ResponseBase(BaseModel):
    success: bool = True
    message: str = "Success"

class DataResponse(ResponseBase, Generic[T]):
    data: Optional[T] = None

class ErrorResponse(ResponseBase):
    success: bool = False
    error_code: Optional[str] = None

class PaginationParams(BaseModel):
    page: int = 1
    limit: int = 10
    
class PaginatedResponse(ResponseBase, Generic[T]):
    data: List[T]
    total: int
    page: int
    limit: int
    total_pages: int


class DataResponseWithPagination(ResponseBase, Generic[T]):
    """DataResponse wrapper that includes pagination metadata."""
    data: List[T] = []
    total: int = 0
    page: int = 1
    limit: int = 10
    total_pages: int = 0


class PaginationMeta(BaseModel):
    """Standalone pagination metadata object."""
    total: int = 0
    page: int = 1
    limit: int = 10
    total_pages: int = 0
