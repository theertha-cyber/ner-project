from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from src.shared.exceptions import AppError
from src.training_service.middleware.tenant_context import TenantContextMiddleware
from src.training_service.celery_app import celery_app
from src.training_service.api.v1 import training_jobs, models


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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


app = FastAPI(
    title="NER Platform Training Service",
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


app.include_router(training_jobs.router)
app.include_router(models.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
