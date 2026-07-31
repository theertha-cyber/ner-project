import re
import uuid
import requests
from datetime import datetime, timezone
from sqlalchemy import text, create_engine
from src.shared.config import settings
from src.extraction_service.celery_app import celery_app
from src.extraction_service.services.document_entity_store import insert_document_entities
from src.extraction_service.services.entity_normalizer import (
    merge_wordpieces,
    reconstruct_entities,
)

_TOKEN_RE = re.compile(r"\S+")


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _tokenize_span(span_text: str, page_number, span_char_start) -> list[dict]:
    """Tokenizes on whitespace (matching str.split() semantics) while attaching each
    token's page number and absolute character offsets, computed from the span's own
    page_number/char_start. Offsets are None when the span carries none."""
    tokens = []
    for m in _TOKEN_RE.finditer(span_text or ""):
        char_start = span_char_start + m.start() if span_char_start is not None else None
        char_end = span_char_start + m.end() if span_char_start is not None else None
        tokens.append({
            "token": m.group(0),
            "page_number": page_number,
            "char_start": char_start,
            "char_end": char_end,
        })
    return tokens


def _align_predictions_with_offsets(predictions: list[dict], token_records: list[dict]) -> list[dict]:
    """Attaches page_number/char_start/char_end from `token_records` (in document
    order) to each prediction by scanning forward for a matching token text,
    tolerating that predictions are a filtered, possibly WordPiece-split subset of
    the original tokens. A prediction whose token text cannot be found from the
    current scan position onward gets NULL offsets rather than aborting."""
    aligned = []
    ptr = 0
    n = len(token_records)
    for pred in predictions:
        tok_text = pred.get("token", "")
        search_text = tok_text[2:] if tok_text.startswith("##") else tok_text
        found_idx = None
        for j in range(ptr, n):
            if token_records[j]["token"] == tok_text or token_records[j]["token"] == search_text:
                found_idx = j
                break
        merged = dict(pred)
        if found_idx is not None:
            merged["page_number"] = token_records[found_idx]["page_number"]
            merged["char_start"] = token_records[found_idx]["char_start"]
            merged["char_end"] = token_records[found_idx]["char_end"]
            ptr = found_idx + 1
        else:
            merged["page_number"] = None
            merged["char_start"] = None
            merged["char_end"] = None
        aligned.append(merged)
    return aligned


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
                SELECT version FROM {schema}.model_versions
                WHERE tenant_id = :tenant_id AND status = 'promoted'
                ORDER BY version DESC
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
                        SELECT text, page_number, char_start FROM {schema}.document_text_spans
                        WHERE document_id = :doc_id
                        ORDER BY span_index NULLS LAST
                    """),
                    {"doc_id": doc_id},
                )
                span_rows = [row for row in result.fetchall() if row[0]]

            token_records = []
            for span_text, page_number, span_char_start in span_rows:
                token_records.extend(_tokenize_span(span_text, page_number, span_char_start))
            tokens = [t["token"] for t in token_records]
            doc_text_preview = " ".join(span_text for span_text, _, _ in span_rows)[:80]
            print(f"WORKER: doc={doc_id} spans={len(span_rows)} tokens={len(tokens)} text_preview={doc_text_preview!r}", flush=True)
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

            aligned_predictions = _align_predictions_with_offsets(predictions, token_records)
            merged_predictions = merge_wordpieces(aligned_predictions)
            normalized_entities = reconstruct_entities(merged_predictions)

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
                insert_document_entities(conn, schema, doc_id, normalized_entities)

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
