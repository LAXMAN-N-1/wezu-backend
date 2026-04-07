from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.models.roles import RoleEnum
from jose import jwt, JWTError, ExpiredSignatureError
from app.core.config import settings
from app.schemas.user import TokenPayload
import logging

logger = logging.getLogger(__name__)

# ── Role priority derived from JWT claims only — no DB hit. ──
_ROLE_PRIORITY = [
    (RoleEnum.ADMIN, RoleEnum.ADMIN.value),
    (RoleEnum.DEALER, RoleEnum.DEALER.value),
    (RoleEnum.DRIVER, RoleEnum.DRIVER.value),
    (RoleEnum.CUSTOMER, RoleEnum.CUSTOMER.value),
]


class RBACMiddleware(BaseHTTPMiddleware):
    """Lightweight auth middleware — decodes JWT, sets ``request.state``
    hints for downstream handlers.  **No database query is performed**;
    the authoritative user load happens once in ``deps.get_current_user``.
    """

    async def dispatch(self, request: Request, call_next):
        # Default states
        request.state.user = None
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
            "/redoc",
        ]

        if any(request.url.path.startswith(p) for p in public_paths):
            return await call_next(request)

        # Try to resolve token and user role from JWT claims only
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(
                    token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
                )
                token_data = TokenPayload(**payload)

                if token_data.sub:
                    # Store the user-id so deps can skip a re-decode when needed
                    request.state.token_user_id = int(token_data.sub)

                    # Derive role hint from JWT "role" claim (set at login)
                    role_claim = (payload.get("role") or "").lower()
                    if role_claim:
                        for role_enum, role_value in _ROLE_PRIORITY:
                            if role_claim == role_value:
                                request.state.user_role = role_enum
                                break

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
