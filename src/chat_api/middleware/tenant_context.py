import uuid
import hashlib
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from src.shared.auth import decode_token
from src.shared.exceptions import AuthError
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
WIDGET_PATHS = {"/api/v1/public/widget.js", "/api/v1/public/chat"}


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        path = request.url.path

        if path in PUBLIC_PATHS:
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

        if self._is_widget_key(token):
            return await self._authenticate_widget(request, call_next, token, request_id)
        return await self._authenticate_jwt(request, call_next, token, request_id)

    def _is_widget_key(self, token: str) -> bool:
        return token.startswith("ner_widget_")

    async def _authenticate_jwt(self, request: Request, call_next, token: str, request_id: str):
        try:
            payload = decode_token(token)
        except AuthError as e:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": str(e), "request_id": request_id}},
            )

        tenant_id = payload.get("tenant_id")
        request.state.user_id = payload.get("user_id")
        request.state.role = payload.get("role")
        request.state.tenant_id = tenant_id
        request.state.auth_method = "jwt"

        if not tenant_id:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": "Token missing tenant_id", "request_id": request_id}},
            )

        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            result = await session.execute(
                text("SELECT status FROM public.tenants WHERE id = :id"),
                {"id": tenant_id},
            )
            row = result.fetchone()
            if not row:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=404,
                    content={"error": {"code": "TENANT_NOT_FOUND", "message": f"Tenant '{tenant_id}' not found", "request_id": request_id}},
                )
            if row[0] == "inactive":
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "TENANT_INACTIVE", "message": "Tenant is deactivated", "request_id": request_id}},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    async def _authenticate_widget(self, request: Request, call_next, token: str, request_id: str):
        key_hash = hashlib.sha256(token.encode()).hexdigest()

        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            result = await session.execute(
                text("SELECT tenant_id, revoked_at FROM public.widget_api_keys WHERE key_hash = :hash"),
                {"hash": key_hash},
            )
            row = result.fetchone()
            if not row:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"error": {"code": "AUTH_ERROR", "message": "Invalid widget API key", "request_id": request_id}},
                )

            tenant_id = row[0]
            revoked_at = row[1]
            if revoked_at is not None:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"error": {"code": "AUTH_ERROR", "message": "Widget API key has been revoked", "request_id": request_id}},
                )

            await session.execute(
                text("UPDATE public.widget_api_keys SET last_used_at = NOW() WHERE key_hash = :hash"),
                {"hash": key_hash},
            )
            await session.commit()

        request.state.tenant_id = tenant_id
        request.state.user_id = None
        request.state.role = "widget"
        request.state.auth_method = "widget_key"

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
