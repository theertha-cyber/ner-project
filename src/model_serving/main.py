import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from src.shared.exceptions import AppError
from src.shared.config import settings
from src.model_serving.middleware.tenant_context import TenantContextMiddleware
from src.model_serving.api.v1 import inference, warmup, rerank

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warms the cross-encoder in the background at startup. Loading it lazily on the
    first /internal/v1/rerank call took longer than the caller's HTTP timeout, so the
    first query after every restart fell back to unranked results — a failure visible
    only as a client-side timeout with an empty message. Warming in a thread rather
    than awaiting it keeps /health responsive while the weights load."""
    warm = asyncio.create_task(asyncio.to_thread(_warm_reranker))
    try:
        yield
    finally:
        warm.cancel()


def _warm_reranker() -> None:
    from src.model_serving.services.rerank_service import _get_reranker

    try:
        _get_reranker()
        logger.info("Reranker warm-up complete: %s", settings.reranker_model)
    except Exception as e:
        logger.warning("Reranker warm-up failed (%s); first rerank call will load it lazily", e)


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
    title="NER Platform Model Serving Layer",
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


app.include_router(inference.router)
app.include_router(warmup.router)
app.include_router(rerank.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
