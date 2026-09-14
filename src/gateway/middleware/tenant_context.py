import re
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from src.shared.auth import decode_token
from src.shared.exceptions import TenantNotFoundError, TenantInactiveError, TenantMismatchError, AuthError
from src.shared.observability import get_request_id, hash_user_id, set_tenant_id, set_user_hash
from src.shared.observability.domain_metrics import record_auth_failure

TENANT_URL_PATTERN = re.compile(r"^/api/v1/tenants/([^/]+)")
WIDGET_PATHS = {"/api/v1/public/widget.js", "/api/v1/public/chat"}


class TenantContextMiddleware(BaseHTTPMiddleware):
    pass

    async def dispatch(self, request: Request, call_next):
        # Generated once, by the shared observability middleware that ran before this
        # one. Read here only so the error bodies below can quote it.
        request_id = get_request_id() or ""

        path = request.url.path

        exempt_paths = {"/health", "/health/live", "/api/v1/auth/login", "/api/v1/auth/refresh", "/docs", "/redoc", "/openapi.json", "/metrics"}
        if path in exempt_paths or path in WIDGET_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            # Counted here rather than in `decode_token`, which never sees this case: a
            # request with no bearer header is turned away before a token exists to
            # validate. The reason is the whole record — the header's actual contents are
            # never read, let alone labelled.
            record_auth_failure("missing_header")
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": "Missing or invalid Authorization header", "request_id": request_id}},
            )
        token = auth_header.removeprefix("Bearer ")
        try:
            payload = decode_token(token)
        except AuthError as e:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": str(e), "request_id": request_id}},
            )

        request.state.user_id = payload.get("user_id")
        request.state.user_email = payload.get("email", payload.get("user_id", ""))
        request.state.role = payload.get("role")
        request.state.token_tenant_id = payload.get("tenant_id")
        # Bind the resolved identity into the ambient context so every record this
        # request produces carries it. Tenant as its UUID from the validated claims,
        # never the slug in the URL; user as an opaque keyed hash.
        set_tenant_id(payload.get("tenant_id"))
        set_user_hash(hash_user_id(payload.get("user_id")))

        tenant_match = TENANT_URL_PATTERN.match(path)
        if tenant_match:
            request.state.tenant_slug = tenant_match.group(1)

        return await call_next(request)
