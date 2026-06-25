from celery import Celery
from sqlalchemy import create_engine, text
from src.shared.config import settings

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
    engine = create_engine(settings.database_url_sync)

    mv_views = [
        "mv_entity_coverage",
        "mv_confidence_distribution",
        "mv_extraction_volume",
        "mv_document_entity_counts",
    ]

    with engine.begin() as conn:
        conn.execute(text(f"SET search_path TO {schema}"))
        for mv in mv_views:
            conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}"))

    engine.dispose()
    return {"tenant_id": tenant_id, "status": "refreshed", "views": mv_views}


@celery_app.task(bind=True, name="handle_extraction_completed", max_retries=3)
def handle_extraction_completed(self, tenant_id: str, extraction_run_id: str | None = None):
    refresh_analytics_materialized_views.delay(tenant_id)
    return {"tenant_id": tenant_id, "extraction_run_id": extraction_run_id, "status": "refresh_triggered"}
