from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("wezu_error_handler")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            request_id = getattr(getattr(request, "state", None), "request_id", "unknown")

            logger.exception(
                "unhandled_exception",
                request_id=request_id,
                path=request.url.path,
                method=request.method,
                error_type=type(e).__name__,
            )

            env = getattr(settings, "ENVIRONMENT", "production")

            if env in ("production", "staging"):
                detail = f"Internal server error. Trace with request_id={request_id}"
            else:
                # Development / testing: include detail for convenience
                detail = str(e)

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "message": "Internal Server Error",
                    "request_id": request_id,
                    "detail": detail,
                },
            )
