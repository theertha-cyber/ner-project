import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from src.shared.auth import decode_token
from src.shared.exceptions import AuthError
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        path = request.url.path

        if request.method == "OPTIONS":
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        exempt_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
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

        tenant_id = payload.get("tenant_id")
        request.state.user_id = payload.get("user_id")
        request.state.role = payload.get("role")
        request.state.tenant_id = tenant_id

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
            if row.status == "inactive":
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "TENANT_INACTIVE", "message": "Tenant is deactivated", "request_id": request_id}},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
