from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from jose import jwt
from app.utils.audit_context import (
    session_ctx, trace_ctx, role_prefix_ctx, user_id_ctx, generate_trace_id
)

class AuditInterceptorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Generate and inject Trace ID
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        trace_ctx.set(trace_id)
        
        try:
            # 2. Extract Context from JWT (Session, Role, User)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    # Extract claims without validating signature (validation happens in deps.py)
                    payload = jwt.get_unverified_claims(token)
                    
                    # Check for advanced audit context
                    session_id = payload.get("session_id")
                    role_prefix = payload.get("role_prefix")
                    user_id = payload.get("sub")
                    
                    if session_id:
                        session_ctx.set(session_id)
                    if role_prefix:
                        role_prefix_ctx.set(role_prefix)
                    if user_id and str(user_id).isdigit():
                        user_id_ctx.set(int(user_id))
                        
                except Exception:
                    pass # Invalid token, ignore here; deps.py will reject it if needed
                    
            # 3. Process Request
            response = await call_next(request)
            
            # 4. Return Trace ID to Client
            response.headers["X-Trace-ID"] = trace_id
            
            return response
        finally:
            # 5. Context Cleanup (Critical for async safety)
            trace_ctx.set(None)
            session_ctx.set(None)
            role_prefix_ctx.set(None)
            user_id_ctx.set(None)
