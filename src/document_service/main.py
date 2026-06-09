from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from src.shared.exceptions import AppError
from src.document_service.middleware.tenant_context import TenantContextMiddleware
from src.document_service.api.v1 import documents


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
    yield


app = FastAPI(
    title="NER Platform Document Ingestion Service",
    version="0.1.0",
    lifespan=lifespan,
)

add_bearer_security(app)
app.add_middleware(TenantContextMiddleware)


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


app.include_router(documents.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
