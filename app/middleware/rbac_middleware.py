from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.deps import get_current_user
from app.models.roles import RoleEnum
from app.core.database import engine
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.config import settings
from app.models.user import TokenPayload, User
from sqlmodel import Session
from sqlalchemy.orm import selectinload
import logging

logger = logging.getLogger(__name__)

class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Default states
        request.state.user = None
        request.state.user_role = None
        
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

        # Try to resolve token and user role
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(
                    token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
                )
                token_data = TokenPayload(**payload)
                
                if token_data.sub:
                    # Provide a fresh DB session for middleware 
                    with Session(engine) as db:
                        user = db.query(User).filter(User.id == int(token_data.sub)).options(selectinload(User.roles)).first()
                        if user and user.is_active:
                            request.state.user = user
                            # Find the highest priority role or the primary role
                            # For granular RBAC, we assign the primary matching Enum
                            role_names = [r.name.lower() for r in user.roles]
                            
                            if RoleEnum.ADMIN.value in role_names:
                                request.state.user_role = RoleEnum.ADMIN
                            elif RoleEnum.DEALER.value in role_names:
                                request.state.user_role = RoleEnum.DEALER
                            elif RoleEnum.DRIVER.value in role_names:
                                request.state.user_role = RoleEnum.DRIVER
                            elif RoleEnum.CUSTOMER.value in role_names:
                                request.state.user_role = RoleEnum.CUSTOMER
                                
            except Exception as e:
                # Middleware shouldn't crash the request on bad tokens if endpoints don't strictly require it.
                # Endpoints that DO require it will fail in their Depends() injection.
                logger.debug(f"Middleware JWT extraction failed: {e}")
                pass
                
        response = await call_next(request)
        return response
