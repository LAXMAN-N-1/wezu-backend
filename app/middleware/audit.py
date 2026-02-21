from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.services.audit_service import audit_service
import time

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Skip non-API requests or health checks if needed
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
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
        
        # 5. Log event asynchronously (don't block the response)
        # However, since audit_service.log_event is async, we can just await it
        # or use background tasks. For simplicity and reliability in this middleware:
        metadata = {
            "method": request.method,
            "url": str(request.url),
            "process_time_ms": int(process_time * 1000),
            "status_code": response.status_code,
            "user_agent": request.headers.get("user-agent"),
        }
        
        # Log to MongoDB
        import asyncio
        asyncio.create_task(
            audit_service.log_event(
                event_type="api_request",
                user_id=user_id,
                resource=request.url.path,
                action=request.method,
                status="success" if response.status_code < 400 else "failure",
                metadata=metadata,
                ip_address=request.client.host if request.client else None
            )
        )
        
        return response
