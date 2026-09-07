from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from src.shared.exceptions import AppError
from src.shared.config import settings
from src.shared.database import get_engine, wait_for_database
from src.shared.readiness import check_database, check_redis, build_readiness_body
from src.training_service.middleware.tenant_context import TenantContextMiddleware
from src.shared.observability import init_observability
from src.shared.observability.propagation import register_queue_depth
from src.training_service.celery_app import celery_app
from src.training_service.api.v1 import training_jobs, models


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_factory = get_engine
    await wait_for_database()
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=settings.cors_allow_private_network,
)

# One call wires logging, tracing, RED metrics, `/metrics` and the shared correlation
# middleware for this process. Mounted last so it is the outermost middleware: the
# correlation identifier has to exist before the tenant middleware builds an error
# body quoting it.
init_observability("training_service", app)
# Queue depth is registered here, on the producer side, and never in a worker:
# depth is a property of the queue, so N workers reporting it would produce N
# identical series that a dashboard could only pick between arbitrarily. See
# design Decision 6. The queue is training never sets `task_default_queue`, so its jobs land on Celery's own default.
register_queue_depth("celery")


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
    checks = {
        "database": await check_database(get_engine()),
        "celery_broker": await check_redis(settings.celery_broker_url),
    }
    status_code, body = build_readiness_body(checks)
    return JSONResponse(status_code=status_code, content=body)


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}
