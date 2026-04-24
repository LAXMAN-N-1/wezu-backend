from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from slowapi.errors import RateLimitExceeded
import logging
import uuid

from app.core.logging import sanitize_for_logging
from app.utils.cors import cors_headers_for_origin

logger = logging.getLogger(__name__)


def _cors_headers_for_request(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin", "")
    return cors_headers_for_origin(origin)


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


def _request_log_context(request: Request) -> dict[str, object]:
    user = getattr(request.state, "user", None)
    # Safely read user.id — the User instance may be detached from its Session
    # after the endpoint's db session is closed, so attribute access can raise
    # DetachedInstanceError.  Fall back to request.state.user_id if so.
    user_id = getattr(request.state, "user_id", None)
    if user_id is None and user is not None:
        try:
            user_id = user.__dict__.get("id")  # read from instance dict, no lazy load
        except Exception:
            pass
    return {
        "request_id": getattr(request.state, "request_id", None),
        "correlation_id": getattr(request.state, "correlation_id", None),
        "method": request.method,
        "path": request.url.path,
        "query_keys": sorted(request.query_params.keys()),
        "client_ip": getattr(request.state, "client_ip", None),
        "user_id": user_id,
        "auth_error": getattr(request.state, "auth_error", None),
    }


def _safe_error_payload(value: object) -> object:
    return sanitize_for_logging(value)


def add_exception_handlers(app: FastAPI):
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        headers = {"X-Request-ID": req_id}
        if getattr(exc, "headers", None):
            headers.update(exc.headers)  # keep WWW-Authenticate and similar headers
        log_context = _request_log_context(request)
        log_context["status_code"] = exc.status_code
        safe_detail = _safe_error_payload(str(exc.detail))
        log_context["detail"] = safe_detail
        if exc.status_code >= 500:
            logger.error("http.exception", extra=log_context)
        elif exc.status_code >= 400:
            logger.warning("http.exception", extra=log_context)
        return make_cors_aware_response(
            request=request,
            status_code=exc.status_code,
            extra_headers=headers,
            content={"error": safe_detail, "code": "HTTP_ERROR", "details": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        safe_errors = _safe_error_payload(exc.errors())
        logger.warning(
            "request.validation_error",
            extra={
                **_request_log_context(request),
                "status_code": 422,
                "validation_errors": safe_errors,
            },
        )
        return make_cors_aware_response(
            request=request,
            status_code=422,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Validation Error", "code": "VALIDATION_ERROR", "details": safe_errors},
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.warning(
            "request.rate_limited",
            extra={**_request_log_context(request), "status_code": 429, "detail": _safe_error_payload(str(exc.detail))},
        )
        return make_cors_aware_response(
            request=request,
            status_code=429,
            extra_headers={"X-Request-ID": req_id},
            content={
                "error": "Too Many Requests",
                "code": "RATE_LIMIT_EXCEEDED",
                "details": _safe_error_payload(str(exc.detail)),
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(
            "request.database_error",
            extra={**_request_log_context(request), "status_code": 500, "error": _safe_error_payload(str(exc))},
            exc_info=True,
        )
        return make_cors_aware_response(
            request=request,
            status_code=500,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Internal Database Error", "code": "DATABASE_ERROR", "details": None},
        )
        
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(
            "request.unhandled_exception",
            extra={**_request_log_context(request), "status_code": 500, "error": _safe_error_payload(str(exc))},
            exc_info=True,
        )
        return make_cors_aware_response(
            request=request,
            status_code=500,
            extra_headers={"X-Request-ID": req_id},
            content={"error": "Internal Server Error", "code": "INTERNAL_ERROR", "details": None},
        )
