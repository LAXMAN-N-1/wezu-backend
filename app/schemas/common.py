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
