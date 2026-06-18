import uuid
import requests
from datetime import datetime, timezone
from sqlalchemy import text, create_engine
from src.shared.config import settings
from src.extraction_service.celery_app import celery_app


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _get_sync_engine():
    return create_engine(settings.database_url_sync)


def _get_documents_to_process(tenant_id: str, doc_ids: list[str]) -> list[str]:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    placeholders = ", ".join(f"'{d}'" for d in doc_ids)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"""
                SELECT id FROM {schema}.documents
                WHERE id IN ({placeholders}) AND status = 'processed'
            """)
        )
        return [row[0] for row in result.fetchall()]


def _get_already_extracted(tenant_id: str, doc_ids: list[str], model_version: str) -> set[str]:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    placeholders = ", ".join(f"'{d}'" for d in doc_ids)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"""
                SELECT DISTINCT e.document_id
                FROM {schema}.extracted_entities e
                JOIN {schema}.extraction_runs r ON e.run_id = r.id
                WHERE e.document_id IN ({placeholders})
                AND r.model_version = :model_version
            """),
            {"model_version": model_version},
        )
        return {row[0] for row in result.fetchall()}


def _get_active_model_version(tenant_id: str) -> str | None:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"""
                SELECT version_number FROM {schema}.model_versions
                WHERE tenant_id = :tenant_id AND status = 'promoted'
                ORDER BY version_number DESC
                LIMIT 1
            """),
            {"tenant_id": tenant_id},
        )
        row = result.fetchone()
        if row:
            return str(row[0])
        return "0"


def _update_run_status(tenant_id: str, run_id: str, status: str, **kwargs):
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    set_clauses = [f"status = :status"]
    params = {"id": run_id, "status": status}
    for key, val in kwargs.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = val
    set_sql = ", ".join(set_clauses)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {schema}.extraction_runs SET {set_sql} WHERE id = :id"),
            params,
        )


@celery_app.task(bind=True, name="run_batch_extraction", max_retries=0)
def run_batch_extraction(self, tenant_id: str, run_id: str, doc_ids: list[str]):
    model_version = _get_active_model_version(tenant_id)
    if model_version is None:
        _update_run_status(tenant_id, run_id, "failed")
        return

    docs = _get_documents_to_process(tenant_id, doc_ids)
    already = _get_already_extracted(tenant_id, doc_ids, model_version)

    to_process = [d for d in docs if d not in already]
    skipped = [d for d in docs if d in already]

    _update_run_status(tenant_id, run_id, "running")

    processed = 0
    failed = 0

    for doc_id in to_process:
        try:
            from src.shared.auth import create_access_token

            engine = _get_sync_engine()
            schema = _schema(tenant_id)

            with engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT text FROM {schema}.document_text_spans
                        WHERE document_id = :doc_id
                        ORDER BY span_index NULLS LAST
                    """),
                    {"doc_id": doc_id},
                )
                spans = [row[0] for row in result.fetchall() if row[0]]

            doc_text = " ".join(spans)
            tokens = doc_text.split()
            print(f"WORKER: doc={doc_id} spans={len(spans)} tokens={len(tokens)} text_preview={doc_text[:80]!r}", flush=True)
            if not tokens:
                failed += 1
                continue

            serving_token = create_access_token(
                tenant_id=tenant_id,
                user_id="extraction-worker",
                role="system_admin",
            )
            infer_url = f"{settings.model_serving_url}/internal/v1/infer"
            infer_resp = requests.post(
                infer_url,
                headers={"Authorization": f"Bearer {serving_token}"},
                json={"tokens": tokens},
                timeout=60,
            )
            if infer_resp.status_code == 404:
                _update_run_status(tenant_id, run_id, "failed")
                return
            infer_resp.raise_for_status()
            body = infer_resp.json()
            predictions = body.get("predictions", [])
            model_version = body.get("model_version", "0")

            with engine.begin() as conn:
                for pred in predictions:
                    conn.execute(
                        text(f"""
                            INSERT INTO {schema}.extracted_entities
                                (id, run_id, document_id, entity_id, value, confidence, review_status)
                            VALUES (:id, :run_id, :document_id, :entity_id, :value, :confidence, 'unreviewed')
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "run_id": run_id,
                            "document_id": doc_id,
                            "entity_id": pred.get("label", "UNKNOWN"),
                            "value": pred.get("token", ""),
                            "confidence": pred.get("confidence", 0.0),
                        },
                    )

            processed += 1

        except Exception as e:
            import traceback
            print(f"EXTRACTION_WORKER_ERROR doc={doc_id}: {e}", flush=True)
            traceback.print_exc()
            failed += 1
            continue

    _update_run_status(
        tenant_id, run_id, "completed",
        completed_at=datetime.now(timezone.utc),
        processed_count=processed,
        skipped_count=len(skipped),
        failed_count=failed,
        model_version=model_version,
    )
