from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.models.roles import RoleEnum
from jose import jwt, JWTError, ExpiredSignatureError
from app.core.config import settings
from app.schemas.user import TokenPayload
import logging

logger = logging.getLogger(__name__)

class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Default states
        request.state.user = None
        request.state.user_id = None
        request.state.user_role = None

        # Never authenticate/authorize CORS preflight requests.
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Skip for openapi and auth
        public_paths = [
            f"{settings.API_V1_STR}/auth/login",
            f"{settings.API_V1_STR}/auth/register",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
        
        if any(request.url.path.startswith(p) for p in public_paths):
            return await call_next(request)

        # Decode JWT to extract user_id for audit/logging.
        # The full User DB query + role resolution is deferred to
        # get_current_user (deps.py) which runs once per request in the
        # FastAPI dependency layer — avoiding a redundant DB round-trip here.
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(
                    token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
                )
                token_data = TokenPayload(**payload)
                
                if token_data.sub:
                    request.state.user_id = int(token_data.sub)
                                
            except ExpiredSignatureError:
                request.state.auth_error = "token_expired"
                logger.warning("rbac.token_decode_failed", extra={"auth_error": "token_expired"})
            except JWTError:
                request.state.auth_error = "token_invalid"
                logger.warning("rbac.token_decode_failed", extra={"auth_error": "token_invalid"})
            except Exception as e:
                request.state.auth_error = "token_invalid"
                logger.warning(
                    "rbac.token_decode_failed",
                    extra={"auth_error": "token_invalid", "error": str(e)},
                )
                
        response = await call_next(request)
        return response
