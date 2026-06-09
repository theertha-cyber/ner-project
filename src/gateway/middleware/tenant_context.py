import re
import uuid
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from src.shared.auth import decode_token
from src.shared.exceptions import TenantNotFoundError, TenantInactiveError, TenantMismatchError, AuthError

TENANT_URL_PATTERN = re.compile(r"^/api/v1/tenants/([^/]+)")


class TenantContextMiddleware(BaseHTTPMiddleware):
    pass

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        path = request.url.path

        exempt_paths = {"/health", "/api/v1/auth/login", "/api/v1/auth/refresh", "/docs", "/redoc", "/openapi.json"}
        if path in exempt_paths:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
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
        request.state.role = payload.get("role")
        request.state.token_tenant_id = payload.get("tenant_id")

        tenant_match = TENANT_URL_PATTERN.match(path)
        if tenant_match:
            request.state.tenant_slug = tenant_match.group(1)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
