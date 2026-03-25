from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.db.session import engine
from sqlmodel import Session
from app.models.audit_log import AuditLog
from fastapi.concurrency import run_in_threadpool
import asyncio
import time

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        start_time = time.time()
        
        user_id = None
        if hasattr(request.state, "user_id"):
             user_id = request.state.user_id
        elif hasattr(request.state, "user"):
             user_id = getattr(request.state.user, "id", None)
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        def save_audit():
            with Session(engine) as db:
                log = AuditLog(
                    action="api_request",
                    user_id=user_id,
                    resource_type="endpoint",
                    resource_id=request.url.path,
                    details=f"method: {request.method}, status: {response.status_code}, time_ms: {int(process_time * 1000)}",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
                db.add(log)
                db.commit()
                
        asyncio.create_task(run_in_threadpool(save_audit))
        
        return response
