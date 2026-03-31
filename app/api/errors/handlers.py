from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
import logging
import uuid

logger = logging.getLogger(__name__)

def add_exception_handlers(app: FastAPI):
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": req_id},
            content={"error": str(exc.detail), "code": "HTTP_ERROR", "details": None}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=422,
            headers={"X-Request-ID": req_id},
            content={"error": "Validation Error", "code": "VALIDATION_ERROR", "details": exc.errors()}
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(f"[{req_id}] Database Error: {exc}")
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": req_id},
            content={"error": "Internal Database Error", "code": "DATABASE_ERROR", "details": None}
        )
        
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(f"[{req_id}] Unhandled Exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": req_id},
            content={"error": "Internal Server Error", "code": "INTERNAL_ERROR", "details": None}
        )
