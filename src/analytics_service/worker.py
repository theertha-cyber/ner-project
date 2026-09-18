from celery import Celery
from sqlalchemy import text
from src.shared.config import settings
from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable, data_plane_retry_countdown
from src.shared.database import get_resolver
from src.shared.observability.domain_metrics import assert_tenant_schema

celery_app = Celery(
    "analytics_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    imports=["src.analytics_service.worker"],
)


@celery_app.task(bind=True, name="refresh_analytics_materialized_views", max_retries=3)
def refresh_analytics_materialized_views(self, tenant_id: str):
    schema = f"tenant_{tenant_id.replace('-', '_')}"
    try:
        # Routed through EngineResolver (ADR-017); never construct an engine from
        # settings.database_url_sync for tenant-schema access. The returned engine is
        # cached by the resolver's LRU — never disposed here, or the cache would be
        # rebuilding a connection on every refresh.
        engine = get_resolver().resolve_sync(tenant_id)

        mv_views = [
            "mv_entity_coverage",
            "mv_confidence_distribution",
            "mv_extraction_volume",
            "mv_document_entity_counts",
        ]

        with engine.begin() as conn:
            assert_tenant_schema(schema, "analytics_service.worker.session")
            conn.execute(text(f"SET search_path TO {schema}"))
            for mv in mv_views:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}"))
    except (DataPlaneUnavailable, DataPlaneNotReady) as exc:
        if self.request.retries < settings.data_plane_task_max_retries:
            raise self.retry(exc=exc, countdown=data_plane_retry_countdown(self.request.retries))
        return {"tenant_id": tenant_id, "status": "failed_retryable", "reason": "data_plane_unavailable"}

    return {"tenant_id": tenant_id, "status": "refreshed", "views": mv_views}


@celery_app.task(bind=True, name="handle_extraction_completed", max_retries=3)
def handle_extraction_completed(self, tenant_id: str, extraction_run_id: str | None = None):
    refresh_analytics_materialized_views.delay(tenant_id)
    return {"tenant_id": tenant_id, "extraction_run_id": extraction_run_id, "status": "refresh_triggered"}
