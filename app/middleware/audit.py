from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.core.config import settings
from app.services.request_audit_queue import request_audit_queue
from app.core.proxy import get_client_ip
import time

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Skip non-API requests or health checks if needed
        excluded_paths = set(settings.LOG_EXCLUDE_PATHS or [])
        excluded_paths.update({"/", "/docs", "/openapi.json"})
        if request.url.path in excluded_paths:
            return await call_next(request)

        start_time = time.time()
        
        # 2. Extract basic info
        user_id = None
        if hasattr(request.state, "user_id"):
             user_id = request.state.user_id
        elif hasattr(request.state, "user"):
             # For cases where getting user object is preferred over just id
             user_id = getattr(request.state.user, "id", None)
        
        # 3. Process request
        response = await call_next(request)
        
        # 4. Calculate duration
        process_time = time.time() - start_time
        
        # 5. Enqueue request audit event without blocking the response path.
        metadata = {
            "method": request.method,
            "path": request.url.path,
            "query_keys": sorted(request.query_params.keys()),
            "process_time_ms": int(process_time * 1000),
            "status_code": response.status_code,
            "user_agent": request.headers.get("user-agent"),
        }

        request_audit_queue.enqueue(
            user_id=user_id,
            action=request.method,
            resource_type="api_request",
            resource_id=request.url.path,
            details=f"Status: {'success' if response.status_code < 400 else 'failure'}",
            metadata=metadata,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        return response
