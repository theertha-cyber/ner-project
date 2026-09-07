import logging
import time
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
from src.shared.observability.domain_metrics import (
    record_extraction_failure,
    record_extraction_job,
    record_extraction_partial_failure,
    record_extraction_stage,
    record_extraction_volume,
)
from src.shared.observability.spans import stage_span
from src.shared.tenant_schema import schema_for_tenant as _schema

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\S+")


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


def _accumulate_entity_counts(entities, counts: dict) -> None:
    """Tally this document's entities by type, for the run span.

    Wrapped so it can never fail the document it is measuring. The counting sits inside
    the per-document `try` that decides `failed_count`, and an exception here would turn a
    successful extraction into a failed one over a telemetry line — which is precisely the
    inversion this whole change is careful to avoid everywhere else.
    """
    try:
        for entity in entities:
            entity_type = getattr(entity, "entity_type", None) or "unknown"
            counts[entity_type] = counts.get(entity_type, 0) + 1
    except Exception:
        logger.debug("entity_type_counts_unavailable", exc_info=True)


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
    """One extraction run, inside one span.

    A wrapper rather than a `with` around the body: the task has seven exits — five early
    returns and two normal ones — and every one of them needs the run's outcome recorded.

    The span carries per-entity-type counts; the metric carries an aggregate only. Entity
    types are tenant-configured, so a type name is neither enumerable at declaration nor
    safe as a label in a store shared across tenants — a tenant that configures
    `policy_holder` and `claim_number` is identifiable from label values alone. The span
    is already tenant-scoped, bounded by trace retention rather than kept for a year, and
    covered by the release-gate scan, so ADR-010's granularity is preserved exactly where
    it is queried. See design Decision 12.
    """
    with stage_span("extraction_run", processing_mode=processing_mode) as span:
        try:
            outcome = _run_batch_extraction(
                self, tenant_id, run_id, doc_ids, processing_mode, span
            )
        except Exception as exc:
            span.set("outcome", "failed")
            span.record_error(exc)
            record_extraction_failure(exc)
            record_extraction_job(tenant_id, "failed")
            raise
        span.set("outcome", outcome)
        record_extraction_job(tenant_id, outcome)
        return None


def _run_batch_extraction(
    self,
    tenant_id: str,
    run_id: str,
    doc_ids: list[str],
    processing_mode: str,
    span,
) -> str:
    run_started = time.monotonic()
    model_version = _get_active_model_version(tenant_id)
    if model_version is None:
        _update_run_status(tenant_id, run_id, "failed")
        record_extraction_stage("inference", time.monotonic() - run_started)
        return "failed"
    span.set("model_version", model_version)

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
        logger.error(
            "extraction_reconcile_failed",
            extra={"run_id": run_id, "error_class": type(e).__name__},
        )
        _update_run_status(tenant_id, run_id, "failed")
        record_extraction_failure(e)
        record_extraction_stage("persist", time.monotonic() - run_started)
        return "failed"

    filenames = _get_document_filenames(tenant_id, to_process)

    processed = 0
    failed = 0
    entities_total = 0
    entities_by_type: dict[str, int] = {}
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
            # No text preview. This line used to print 80 characters of the document's
            # own span text, which is tenant personal data, straight to stdout — where
            # no logging filter can reach it. The counts are what the line was read for.
            logger.info(
                "document_tokenized",
                extra={"doc_id": doc_id, "spans": len(span_rows), "tokens": len(tokens)},
            )
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
                record_extraction_stage("inference", time.monotonic() - run_started)
                return "failed"
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
                logger.warning(
                    "semantic_values_unparseable",
                    extra={"doc_id": doc_id, "unparseable": unparseable_count},
                )

            normalized_entities, rejected_count = filter_valid_entities(normalized_entities)
            if rejected_count:
                logger.warning(
                    "entities_rejected_invalid",
                    extra={"doc_id": doc_id, "rejected": rejected_count},
                )
            before_collapse = len(normalized_entities)
            normalized_entities = collapse_duplicates(normalized_entities)
            collapsed_count = before_collapse - len(normalized_entities)
            if collapsed_count:
                logger.info(
                    "duplicate_entities_collapsed",
                    extra={"doc_id": doc_id, "collapsed": collapsed_count},
                )
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
                    # `outcome.discarded` holds rejected candidate *values*. Only how
                    # many were discarded may be recorded, never which.
                    logger.warning(
                        "postprocess_degraded",
                        extra={"doc_id": doc_id, "discarded": len(outcome.discarded)},
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
            _accumulate_entity_counts(normalized_entities, entities_by_type)
            entities_total += len(normalized_entities)

        except Exception as e:
            # `exc_info` rather than the interpolated exception: a driver or model
            # error quotes the offending value back, and the traceback goes through
            # the formatter rather than straight to stdout.
            logger.error(
                "extraction_document_failed",
                extra={"doc_id": doc_id, "error_class": type(e).__name__},
                exc_info=True,
            )
            failed += 1
            # A document that failed inside a run that continues: the run is partial, not
            # dead, and the two are different operational facts.
            record_extraction_partial_failure("inference")
            record_extraction_failure(e)
            continue

    if rejected_total:
        logger.warning(
            "entities_rejected_invalid_total",
            extra={"run_id": run_id, "rejected_total": rejected_total},
        )

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

    record_extraction_stage("persist", time.monotonic() - run_started)
    record_extraction_volume(pages=processed, entities=entities_total)
    span.set("documents_processed", processed)
    span.set("documents_failed", failed)
    span.set("documents_skipped", len(skipped))
    span.set("entities_extracted", entities_total)
    span.set("retries", getattr(self.request, "retries", 0) if hasattr(self, "request") else 0)
    # ADR-010 measures dataset readiness per entity type, so the per-type breakdown has to
    # survive somewhere. It survives here, as a span attribute, and nowhere else.
    for entity_type, count in sorted(entities_by_type.items()):
        span.set(f"entities.{entity_type}", count)
    return "partial" if failed else "succeeded"
