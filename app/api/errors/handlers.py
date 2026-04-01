from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
import logging
import uuid

logger = logging.getLogger(__name__)

def _cors_headers_for_request(request: Request) -> dict[str, str]:
    origin = (request.headers.get("origin") or "")
    if not origin:
        return {}
    if settings.is_origin_allowed(origin):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def make_cors_aware_response(
    request: Request,
    status_code: int,
    content: dict,
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    headers = _cors_headers_for_request(request)
    if extra_headers:
        headers.update({k: v for k, v in extra_headers.items() if v is not None})
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def add_exception_handlers(app: FastAPI):
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        headers = {"X-Request-ID": req_id}
        if getattr(exc, "headers", None):
            headers.update(exc.headers)  # keep WWW-Authenticate and similar headers
        return make_cors_aware_response(
            request=request,
            status_code=exc.status_code,
            extra_headers=headers,
            content={"error": str(exc.detail), "code": "HTTP_ERROR", "details": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return make_cors_aware_response(
            request=request,
            status_code=422,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Validation Error", "code": "VALIDATION_ERROR", "details": exc.errors()},
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return make_cors_aware_response(
            request=request,
            status_code=429,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Too Many Requests", "code": "RATE_LIMIT_EXCEEDED", "details": str(exc.detail)},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(f"[{req_id}] Database Error: {exc}")
        return make_cors_aware_response(
            request=request,
            status_code=500,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Internal Database Error", "code": "DATABASE_ERROR", "details": None},
        )
        
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(f"[{req_id}] Unhandled Exception: {exc}", exc_info=True)
        return make_cors_aware_response(
            request=request,
            status_code=500,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Internal Server Error", "code": "INTERNAL_ERROR", "details": None},
        )
