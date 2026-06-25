from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from src.shared.exceptions import AppError
from src.gateway.api.v1 import admin, auth, entity_types, users, extraction_proxy, dashboard, chat_proxy, analytics_proxy
from src.gateway.middleware.tenant_context import TenantContextMiddleware
from src.shared.database import get_engine
from src.shared.config import settings


def add_bearer_security(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["components"]["securitySchemes"] = {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        for path in schema["paths"].values():
            for method in path.values():
                method["security"] = [{"bearerAuth": []}]
        app.openapi_schema = schema
        return app.openapi_schema
    app.openapi = custom_openapi


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_factory = get_engine
    yield


app = FastAPI(
    title="NER Platform API Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

add_bearer_security(app)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=settings.cors_allow_private_network,
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
    )


app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(entity_types.router)
app.include_router(users.router)
app.include_router(extraction_proxy.router)
app.include_router(dashboard.router)
app.include_router(chat_proxy.router)
app.include_router(analytics_proxy.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
