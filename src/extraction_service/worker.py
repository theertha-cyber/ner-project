import re
import uuid
import requests
from datetime import datetime, timezone
from sqlalchemy import text, create_engine
from src.shared.config import settings
from src.extraction_service.celery_app import celery_app
from src.extraction_service.services.document_entity_store import (
    delete_document_entities,
    insert_document_entities,
)
from src.extraction_service.services.entity_normalizer import (
    collapse_duplicates,
    filter_valid_entities,
    merge_wordpieces,
    reconstruct_entities,
)
from src.extraction_service.services.entity_postprocessor import postprocess_document
from src.extraction_service.services.entity_store import get_already_extracted
from src.extraction_service.services.processing_modes import (
    DEFAULT_PROCESSING_MODE,
    ProcessingMode,
)
from src.extraction_service.services.relational_projection import (
    delete_relational_entities,
    project_document_entities,
)
from src.extraction_service.services.semantic_normalizer import (
    apply_semantic_normalization,
    load_entity_definition_specs,
    load_entity_type_config,
)
from src.shared.entity_views import reconcile_entity_tables_sync

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
    order) to each prediction.

    A prediction carrying `word_index` (the fine-tuned model-serving path) is mapped
    directly onto that index — exact, and immune to the same word recurring in the
    document. Sliding-window inference makes this mandatory rather than merely
    nicer: windows re-read overlapping text, so text-scanning alone can no longer be
    trusted to land on the occurrence the model actually labelled.

    Predictions without `word_index` (the base-model pipeline path, whose outputs are
    WordPieces) fall back to scanning forward for a matching token text. A prediction
    that cannot be placed gets NULL offsets rather than aborting."""
    aligned = []
    ptr = 0
    n = len(token_records)
    for pred in predictions:
        word_index = pred.get("word_index")
        if word_index is not None and 0 <= word_index < n:
            record = token_records[word_index]
            merged = dict(pred)
            merged["page_number"] = record["page_number"]
            merged["char_start"] = record["char_start"]
            merged["char_end"] = record["char_end"]
            aligned.append(merged)
            ptr = word_index + 1
            continue

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
                WHERE id IN ({placeholders}) AND status = 'processed' AND purpose = 'query'
            """)
        )
        return [row[0] for row in result.fetchall()]


def _get_document_filenames(tenant_id: str, doc_ids: list[str]) -> dict[str, str]:
    """`document_id -> filename`, for the denormalized `filename` column on `subject`.

    Read separately rather than by widening `_get_documents_to_process`, whose `list[str]`
    return type the eligibility arithmetic below depends on. `filename` is carried on `subject`
    so generated SQL can name a document without joining `documents` — a join the model has to
    get right on every question that mentions a file."""
    if not doc_ids:
        return {}
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT id, filename FROM {schema}.documents WHERE id = ANY(:ids)"),
            {"ids": list(doc_ids)},
        )
        return {row[0]: row[1] for row in result.fetchall()}


def _get_cached_model_version(tenant_id: str) -> str:
    """Promoted version from the local `model_versions` cache. Reads `version_number`
    — `version` is a legacy column that is NULL on every row, and `str(None)` from it
    silently produced the version string "None", matching no extraction run and making
    every document look never-extracted. Only reached when the registry is unreachable;
    the cache can lag MLflow, so it is the fallback, not the authority."""
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
        if row and row[0] is not None:
            return str(row[0])
        return "0"


def _get_active_model_version(tenant_id: str) -> str:
    """Active model version, resolved from the training-service registry — the same
    authority `model_serving._resolve_active_version` consults before stamping
    `model_version` onto an inference response, and hence onto
    `extraction_runs.model_version`. Both the worker's skip set and the
    eligible-documents endpoint compare against those recorded runs, so they must
    resolve the version the same way the runs were labelled or they can never match.
    Returns "0" when no model is promoted (matching the registry's base-model
    `version_number`)."""
    from src.shared.auth import create_access_token

    token = create_access_token(
        tenant_id=tenant_id, user_id="extraction-service", role="system_admin"
    )
    registry_url = f"{settings.training_service_url.rstrip('/')}/api/v1/models/active"
    try:
        resp = requests.get(
            registry_url,
            headers={"Authorization": f"Bearer {token}"},
            params={"tenant_id": tenant_id},
            timeout=10,
        )
        if resp.status_code == 200:
            version_number = resp.json().get("version_number")
            if version_number is not None:
                return str(version_number)
    except (requests.RequestException, ValueError):
        pass
    return _get_cached_model_version(tenant_id)


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
def run_batch_extraction(
    self,
    tenant_id: str,
    run_id: str,
    doc_ids: list[str],
    processing_mode: str = DEFAULT_PROCESSING_MODE.value,
):
    model_version = _get_active_model_version(tenant_id)
    if model_version is None:
        _update_run_status(tenant_id, run_id, "failed")
        return

    docs = _get_documents_to_process(tenant_id, doc_ids)
    # Idempotency is decided by model version alone. The processing mode deliberately
    # plays no part: flipping the UI toggle must not silently reprocess and overwrite
    # entities a previous run already produced.
    already = get_already_extracted(tenant_id, doc_ids, model_version)

    to_process = [d for d in docs if d not in already]
    skipped = [d for d in docs if d in already]

    _update_run_status(tenant_id, run_id, "running")

    # The catalog and the generated schema are settled once, here, before any document is
    # touched. Reconciliation runs in its **own** transaction: inside a per-document one it
    # would hold schema locks for the length of that document's writes and couple the schema
    # state to a single document's success. It is not optional and not a nicety —
    # `TenantService.create_tenant` clones `tenant_template` via `pg_tables` + `CREATE TABLE
    # (LIKE ...)`, so a freshly provisioned tenant starts with zero generated tables and its
    # first run would otherwise fail every document.
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    try:
        with engine.connect() as conn:
            entity_specs = load_entity_definition_specs(conn, tenant_id)
        with engine.begin() as conn:
            reconcile_entity_tables_sync(conn, schema, entity_specs)
    except Exception as e:
        # Every document would fail at projection anyway, and leaving the run at "running"
        # forever hides why. Same shape as the missing-model and missing-serving paths above.
        print(f"EXTRACTION_WORKER_ERROR run={run_id} reconcile_failed: {e}", flush=True)
        _update_run_status(tenant_id, run_id, "failed")
        return

    filenames = _get_document_filenames(tenant_id, to_process)

    processed = 0
    failed = 0
    rejected_total = 0
    postprocess_degraded = False
    # A run-level ceiling rather than a per-document one: exhausting it degrades the
    # remainder of the run to BERT-only instead of stalling or failing it.
    postprocess_budget_remaining = settings.postprocess_token_budget

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
            # `token_records` carries the `O` words model serving filtered out, so an
            # entity whose tokens straddle a small gap reads back as the document's own
            # text ("two and a half years") rather than the labelled fragments.
            normalized_entities = reconstruct_entities(merged_predictions, token_records)

            with engine.connect() as conn:
                type_config = load_entity_type_config(conn, tenant_id)
            normalized_entities, unparseable_count = apply_semantic_normalization(normalized_entities, type_config)
            if unparseable_count:
                print(f"WORKER: doc={doc_id} semantic_unparseable={unparseable_count}", flush=True)

            normalized_entities, rejected_count = filter_valid_entities(normalized_entities)
            if rejected_count:
                print(f"WORKER: doc={doc_id} rejected_invalid={rejected_count}", flush=True)
            before_collapse = len(normalized_entities)
            normalized_entities = collapse_duplicates(normalized_entities)
            collapsed_count = before_collapse - len(normalized_entities)
            if collapsed_count:
                print(f"WORKER: doc={doc_id} collapsed_duplicates={collapsed_count}", flush=True)
            rejected_total += rejected_count

            if processing_mode == ProcessingMode.BERT_LLM_POSTPROCESS.value:
                # Runs after deduplication so the token spend is proportional to distinct
                # facts, and after the validity gate so obvious artifacts are already
                # gone. Never raises: a failure marks the run degraded and keeps the
                # deterministic result.
                outcome, tokens_used = postprocess_document(
                    normalized_entities,
                    token_records,
                    type_config,
                    {name.upper() for name in type_config},
                    token_budget_remaining=postprocess_budget_remaining,
                )
                postprocess_budget_remaining -= tokens_used
                normalized_entities = collapse_duplicates(outcome.entities)
                if outcome.degraded:
                    postprocess_degraded = True
                    print(
                        f"WORKER: doc={doc_id} postprocess_degraded reasons={outcome.discarded[:3]}",
                        flush=True,
                    )

            with engine.begin() as conn:
                # Full replace, so a re-run is idempotent. `get_already_extracted` is scoped by
                # model version, so a new model legitimately makes every document eligible
                # again — and `document_entities` has no `run_id`, no `model_version`, and no
                # unique constraint, so without the delete the two generations would be
                # indistinguishable. The relational delete covers **every** existing generated
                # table, including deactivated definitions', or their stale rows would survive
                # to be re-exposed on reactivation.
                delete_document_entities(conn, schema, doc_id)
                delete_relational_entities(conn, schema, doc_id, entity_specs)

                # `extracted_entities` is deliberately NOT deleted: it is the idempotency
                # ledger `get_already_extracted` joins against, and duplication across runs is
                # the per-run audit trail rather than a defect.
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
                # Same list, same transaction. The relational surface is either consistent with
                # `document_entities` or absent for this document — never partially written. A
                # missing table or column raises here, which fails the document and rolls all
                # five writes back rather than reporting a success over an incomplete surface.
                project_document_entities(
                    conn,
                    schema,
                    doc_id,
                    filenames.get(doc_id),
                    normalized_entities,
                    entity_specs,
                )

            processed += 1

        except Exception as e:
            import traceback
            print(f"EXTRACTION_WORKER_ERROR doc={doc_id}: {e}", flush=True)
            traceback.print_exc()
            failed += 1
            continue

    if rejected_total:
        print(f"WORKER: run={run_id} rejected_invalid_total={rejected_total}", flush=True)

    run_fields = {
        "completed_at": datetime.now(timezone.utc),
        "processed_count": processed,
        "skipped_count": len(skipped),
        "failed_count": failed,
        "model_version": model_version,
        "processing_mode": processing_mode,
    }
    if processing_mode == ProcessingMode.BERT_LLM_POSTPROCESS.value:
        run_fields["postprocess_model"] = settings.azure_openai_chat_deployment
        run_fields["postprocess_prompt_version"] = settings.postprocess_prompt_version
        run_fields["postprocess_degraded"] = postprocess_degraded

    # A post-processing failure never fails the run: it is an optional enhancement over
    # a successful extraction, and `max_retries=0` means a failed run is not retried.
    # The degraded flag plus the per-row `postprocess_status` carry what went wrong.
    _update_run_status(tenant_id, run_id, "completed", **run_fields)
