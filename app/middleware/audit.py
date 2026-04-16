from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.services.audit_service import audit_service
from app.core.proxy import get_client_ip
import time
import traceback

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Skip non-API requests or health checks if needed
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        from app.utils.data_masking import mask_dict
        start_time = time.time()
        
        # 2. Extract basic info
        user_id = None
        if hasattr(request.state, "user_id"):
             user_id = request.state.user_id
        elif hasattr(request.state, "user"):
             user_id = getattr(request.state.user, "id", None)
        
        response = None
        status = "success"
        error_metadata = {}
        
        try:
            # 3. Process request
            response = await call_next(request)
            if response.status_code >= 400:
                status = "failure"
        except Exception as e:
            # 4. Handle uncaught exceptions (Critical for failure logging)
            status = "failure"
            error_metadata = {
                "exception": str(e),
                "traceback": traceback.format_exc()
            }
            # Re-raise to let exception handlers deal with it, but we log first
            raise e
        finally:
            # 5. Calculate duration
            process_time_ms = int((time.time() - start_time) * 1000)
            
            # 6. Capture Masked Headers
            masked_headers = mask_dict(dict(request.headers))
            
            metadata = {
                "method": request.method,
                "url": str(request.url),
                "process_time_ms": process_time_ms,
                "status_code": response.status_code if response else 500,
                "user_agent": request.headers.get("user-agent"),
                "headers": masked_headers,
                **error_metadata
            }
            
            # Determine appropriate log level
            level = "INFO"
            if response:
                if response.status_code >= 500:
                    level = "ERROR"
                elif response.status_code >= 400:
                    level = "WARNING"
            else:
                level = "ERROR"

            # 7. Log event asynchronously
            import asyncio
            asyncio.create_task(
                audit_service.log_event(
                    event_type="api_request",
                    user_id=user_id,
                    resource=request.url.path,
                    action=request.method,
                    status=status,
                    metadata=metadata,
                    response_time_ms=float(process_time_ms),
                    module="api"
                )
            )
        
        return response
