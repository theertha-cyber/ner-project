"""The LLM pre-labeling background task.

Everything the request path must not wait on: the provider call, grounding, and the write to
`suggested_spans`. The trigger endpoint has already decided this document is eligible and has
already missed the cache, so this task's job is to do the work and record what happened on the
job row — including when it fails, because a job that goes quiet is indistinguishable from a
document that genuinely contains no entities.

Tenant isolation (ADR-001): the tenant id arrives as a task argument and every statement below
is built from `_schema(tenant_id)` or filters `entity_definitions` by it. Nothing here reads a
tenant from ambient state, and one task only ever sees one tenant's document and configuration.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from src.annotation_service.celery_app import celery_app
from src.annotation_service.services.llm_client import LLMUnavailable, get_llm_client
from src.annotation_service.services.llm_review import LLMReviewError, review_prediction
from src.annotation_service.services.review_resolution import (
    ORIGIN_QUEUE,
    resolve_prediction,
)
from src.annotation_service.services.llm_prelabel import (
    SYSTEM_PROMPT,
    build_user_payload,
    ground_entities,
    parse_llm_response,
)
from src.annotation_service.services.schema_proposal import (
    build_user_payload as build_proposal_payload,
    propose_candidates,
    resolve_max_candidates as resolve_proposal_max_candidates,
    system_prompt_for as schema_proposal_system_prompt_for,
)
from src.shared.auth import create_access_token
from src.shared.config import settings
from src.shared.confidence_routing import ROUTE_LLM, resolve_review_policy
from src.shared.entity_config_version import (
    load_active_entity_config,
    load_active_entity_config_sync,
)


def _schema(tenant_id: str) -> str:
    """The same derivation every `annotation_service` endpoint uses."""
    return f"tenant_{tenant_id.replace('-', '_')}"


def _make_service_token(tenant_id: str) -> str:
    """Service-to-service credential, matching `training_service.worker`'s pattern.

    This task reads and writes its own database directly and so needs no cross-service call
    today. The helper is here, rather than invented at the first call site that needs one, so a
    later addition follows the established pattern instead of a new one."""
    return create_access_token(
        tenant_id=tenant_id,
        user_id="annotation-llm-worker",
        role="system_admin",
    )


def _get_sync_engine():
    return create_engine(settings.database_url_sync)


def _now():
    return datetime.now(timezone.utc)


def load_document_text(connection, schema: str, doc_id: str) -> str:
    """The document's extracted text, in span order.

    The keyword path reads only the first span; this reads all of them, because the LLM is
    given the whole document and an offset must be valid against exactly the text that was
    sent."""
    rows = connection.execute(
        text(
            f"SELECT text FROM {schema}.document_text_spans "
            "WHERE document_id = :doc_id ORDER BY span_index"
        ),
        {"doc_id": doc_id},
    ).fetchall()
    return "".join(row[0] or "" for row in rows)


def replace_suggested_spans(connection, schema: str, doc_id: str, spans: list[dict]) -> None:
    """Replace, not merge — the same contract the keyword path has always had.

    A document's suggestions describe one run of one mechanism. Merging would leave a reviewer
    looking at a mix of two runs with no way to tell which claim came from where."""
    connection.execute(
        text(f"DELETE FROM {schema}.suggested_spans WHERE document_id = :doc_id"),
        {"doc_id": doc_id},
    )
    for span in spans:
        connection.execute(
            text(
                f"INSERT INTO {schema}.suggested_spans "
                "(id, document_id, entity_type, char_start, char_end, text_content, "
                " confidence, source) "
                "VALUES (:id, :doc_id, :entity_type, :char_start, :char_end, :text_val, "
                "        :confidence, :source)"
            ),
            {
                "id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "entity_type": span["entity_type"],
                "char_start": span["char_start"],
                "char_end": span["char_end"],
                "text_val": span["text"],
                "confidence": span["confidence"],
                "source": span["source"],
            },
        )


def _mark_running(connection, schema: str, job_id: str) -> None:
    connection.execute(
        text(f"UPDATE {schema}.llm_prelabel_jobs SET status = 'running' WHERE id = :id"),
        {"id": job_id},
    )


def _mark_completed(connection, schema: str, job_id: str, spans, counts) -> None:
    connection.execute(
        text(
            f"UPDATE {schema}.llm_prelabel_jobs "
            "SET status = 'completed', spans = CAST(:spans AS JSONB), "
            "    counts = CAST(:counts AS JSONB), completed_at = :now "
            "WHERE id = :id"
        ),
        {
            "id": job_id,
            "spans": json.dumps(spans),
            "counts": json.dumps(counts),
            "now": _now(),
        },
    )


def _mark_failed(connection, schema: str, job_id: str, message: str) -> None:
    connection.execute(
        text(
            f"UPDATE {schema}.llm_prelabel_jobs "
            "SET status = 'failed', error_message = :message, completed_at = :now "
            "WHERE id = :id"
        ),
        {"id": job_id, "message": message[:2000], "now": _now()},
    )


def extract_and_ground_document(engine, tenant_id: str, doc_id: str, client, guidance_text: str = ""):
    """One document through the provider and the grounder. The only implementation of it.

    Everything between "which document" and "which spans" lives here, so the batch task
    (`run_prelabel_batch_sync`) runs exactly this rather than a second, simplified copy of it.
    Two copies would be free to drift, and the thing they would drift on is the extractive-only
    guarantee — the batch path silently accepting a paraphrase the single-document path drops
    is the failure verification.md Risk 2 exists to catch (design.md Decision 2).

    Storage is left to the caller. Each caller has its own bookkeeping row to write — a job for
    the single-document path, a per-document batch outcome for the batch — and writing the spans
    in the same transaction as that row is what keeps the two from disagreeing. The provider
    call sits deliberately between the two transactions rather than inside one: it has a 60
    second timeout, and holding a transaction open across it would pin a connection for the
    duration.
    """
    schema = _schema(tenant_id)

    with engine.begin() as connection:
        document_text = load_document_text(connection, schema, doc_id)
        entity_types = load_active_entity_config_sync(connection, tenant_id)

    response = client.complete_json(
        SYSTEM_PROMPT,
        build_user_payload(document_text, entity_types, guidance_text=guidance_text),
    )

    return ground_entities(
        document_text,
        parse_llm_response(response),
        [entity_type["name"] for entity_type in entity_types],
    )


def run_llm_prelabel_sync(tenant_id: str, doc_id: str, job_id: str, llm_client=None) -> dict:
    """The task body, callable without Celery.

    Split out from the task so the pipeline can be exercised end to end — real database, stubbed
    provider — without a broker. `llm_client` is a parameter for the same reason: the provider is
    the one thing tests must not reach.
    """
    schema = _schema(tenant_id)
    client = llm_client if llm_client is not None else get_llm_client()
    engine = _get_sync_engine()

    with engine.begin() as connection:
        _mark_running(connection, schema, job_id)

    try:
        result = extract_and_ground_document(engine, tenant_id, doc_id, client)
    except LLMUnavailable as exc:
        with engine.begin() as connection:
            _mark_failed(connection, schema, job_id, str(exc))
        raise

    with engine.begin() as connection:
        replace_suggested_spans(connection, schema, doc_id, result.spans)
        _mark_completed(connection, schema, job_id, result.spans, result.counts())

    return result.counts()


@celery_app.task(bind=True, name="run_llm_prelabel", max_retries=0)
def run_llm_prelabel(self, tenant_id: str, doc_id: str, job_id: str):
    return run_llm_prelabel_sync(tenant_id, doc_id, job_id)


# ---------------------------------------------------------------------------
# Entity schema proposal (seed-bootstrap group 2)
# ---------------------------------------------------------------------------


def _load_seed_documents(connection, schema: str, doc_ids: list[str]) -> list[dict]:
    """Each seed document's full extracted text, in the order the caller submitted them.

    Reconstructed span by span, the same way `load_document_text` does for pre-labeling, for the
    same reason: the first span is page one, and a schema derived from page one of a multi-page
    document is a schema of page one."""
    documents = []
    for doc_id in doc_ids:
        documents.append(
            {"document_id": doc_id, "text": load_document_text(connection, schema, doc_id)}
        )
    return documents


def _mark_proposal_running(connection, schema: str, proposal_id: str) -> None:
    connection.execute(
        text(f"UPDATE {schema}.schema_proposals SET status = 'running' WHERE id = :id"),
        {"id": proposal_id},
    )


def _mark_proposal_failed(connection, schema: str, proposal_id: str, message: str) -> None:
    connection.execute(
        text(
            f"UPDATE {schema}.schema_proposals "
            "SET status = 'failed', error_message = :message, completed_at = :now WHERE id = :id"
        ),
        {"id": proposal_id, "message": message[:2000], "now": _now()},
    )


def run_schema_proposal_sync(tenant_id: str, proposal_id: str, llm_client=None) -> dict:
    """Generate a schema proposal and store its candidates.

    Note what this does not do: it writes `schema_proposal_candidates` and nothing else. No
    statement in this function touches `public.entity_definitions`, and that absence is the
    whole of design.md Decision 1 — an entity type comes into existence when a human approves a
    candidate and the entity-config API creates it, never as a side effect of a model run
    (verification.md Risk 1)."""
    schema = _schema(tenant_id)
    client = llm_client if llm_client is not None else get_llm_client()
    engine = _get_sync_engine()

    with engine.begin() as connection:
        _mark_proposal_running(connection, schema, proposal_id)
        row = connection.execute(
            text(
                f"SELECT seed_document_ids, qa_pair_document_id "
                f"FROM {schema}.schema_proposals WHERE id = :id"
            ),
            {"id": proposal_id},
        ).fetchone()
        seed_ids = row[0] if row else []
        if isinstance(seed_ids, str):
            seed_ids = json.loads(seed_ids)
        seed_documents = _load_seed_documents(connection, schema, seed_ids or [])
        entity_types = load_active_entity_config_sync(connection, tenant_id)
        qa_pair_id = row[1] if row else None
        qa_pair_text = None
        if qa_pair_id:
            qa_docs = _load_seed_documents(connection, schema, [qa_pair_id])
            qa_pair_text = qa_docs[0]["text"] if qa_docs else None

    # A Q&A-pair document turns the proposal from schema discovery into schema transcription:
    # one entity type per Q&A pair, kept even when no seed document contains a value for it.
    # The candidate cap then follows how many pairs the tenant actually wrote (20 pairs -> ~25,
    # 50 pairs -> ~55), rather than a fixed number.
    qa_driven = bool((qa_pair_text or "").strip())
    # In discovery mode this returns the fixed default; in Q&A-driven mode it follows the pair
    # count (20 pairs -> ~25, 50 -> ~55).
    max_candidates = resolve_proposal_max_candidates(qa_pair_text if qa_driven else None)

    try:
        response = client.complete_json(
            schema_proposal_system_prompt_for(qa_pair_text, max_candidates),
            build_proposal_payload(
                seed_documents, entity_types, qa_pair_text=qa_pair_text, qa_driven=qa_driven
            ),
        )
    except LLMUnavailable as exc:
        with engine.begin() as connection:
            _mark_proposal_failed(connection, schema, proposal_id, str(exc))
        raise

    result = propose_candidates(
        response,
        seed_documents,
        require_grounding=not qa_driven,
        max_candidates=max_candidates,
    )

    with engine.begin() as connection:
        for candidate in result.candidates:
            connection.execute(
                text(
                    f"INSERT INTO {schema}.schema_proposal_candidates "
                    "(id, proposal_id, name, description, examples, disposition) "
                    "VALUES (:id, :proposal_id, :name, :description, "
                    "        CAST(:examples AS JSONB), 'pending')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "proposal_id": proposal_id,
                    "name": candidate["name"],
                    "description": candidate["description"],
                    "examples": json.dumps(candidate["examples"]),
                },
            )
        connection.execute(
            text(
                f"UPDATE {schema}.schema_proposals "
                "SET status = 'completed', completed_at = :now WHERE id = :id"
            ),
            {"id": proposal_id, "now": _now()},
        )

    return result.counts()


@celery_app.task(bind=True, name="run_schema_proposal", max_retries=0)
def run_schema_proposal(self, tenant_id: str, proposal_id: str):
    return run_schema_proposal_sync(tenant_id, proposal_id)


# ---------------------------------------------------------------------------
# Batch pre-labeling (seed-bootstrap group 3)
# ---------------------------------------------------------------------------


def _mark_batch_document(
    connection, schema: str, batch_id: str, doc_id: str, status: str, counts=None, error=None
) -> None:
    connection.execute(
        text(
            f"UPDATE {schema}.prelabel_batch_documents "
            "SET status = :status, counts = CAST(:counts AS JSONB), error_message = :error, "
            "    completed_at = :now "
            "WHERE batch_id = :batch_id AND document_id = :doc_id"
        ),
        {
            "status": status,
            "counts": json.dumps(counts) if counts is not None else None,
            "error": error[:2000] if error else None,
            "now": _now(),
            "batch_id": batch_id,
            "doc_id": doc_id,
        },
    )


def _auto_promote_large_batch(connection, schema: str, tenant_id: str, batch_id: str) -> int:
    """Promote every suggestion from a finished `large` batch straight to confirmed spans.

    A `large` batch is never reviewed by anyone (annotation-workflow-review-simplification
    design.md Decision 1) — the moment the pre-labeling job finishes, its output *is* the
    training data. This is the one place that happens, so it must be idempotent against a
    retried task: the `training_eligible_at IS NULL` guard below makes a second call a no-op.

    `span_batch_provenance.acceptance_id` is `NOT NULL` (migration 039), so an auto-promoted
    span still needs an acceptance record to point at — there was never a human review, so this
    writes one with `reviewer = NULL` and `sampled = false`, which is what distinguishes an
    auto-promoted batch's provenance from a reviewed one on inspection, without a schema change.
    """
    from src.shared.config import settings as _settings

    claimed = connection.execute(
        text(
            f"UPDATE {schema}.prelabel_batches "
            "SET training_eligible_at = NOW(), annotator_review_status = 'approved' "
            "WHERE id = :id AND training_eligible_at IS NULL "
            "RETURNING id"
        ),
        {"id": batch_id},
    ).fetchone()
    if claimed is None:
        return 0

    acceptance_id = str(uuid.uuid4())
    connection.execute(
        text(
            f"INSERT INTO {schema}.batch_acceptance_records "
            "(id, batch_id, sampled_document_ids, sample_size, sampled, "
            " agreement_threshold, decision, reviewer, decided_at) "
            "VALUES (:id, :batch_id, '[]'::jsonb, 0, false, :threshold, 'accepted', NULL, NOW())"
        ),
        {
            "id": acceptance_id,
            "batch_id": batch_id,
            "threshold": _settings.seed_bootstrap_agreement_threshold,
        },
    )

    doc_ids = [
        row[0]
        for row in connection.execute(
            text(
                f"SELECT document_id FROM {schema}.prelabel_batch_documents "
                "WHERE batch_id = :batch_id"
            ),
            {"batch_id": batch_id},
        ).fetchall()
    ]
    suggestions = connection.execute(
        text(
            f"SELECT id, document_id, entity_type, char_start, char_end, text_content, "
            f"       confidence FROM {schema}.suggested_spans "
            "WHERE document_id = ANY(:doc_ids)"
        ),
        {"doc_ids": doc_ids},
    ).fetchall()

    promoted = 0
    for suggestion in suggestions:
        span_id = str(uuid.uuid4())
        connection.execute(
            text(
                f"INSERT INTO {schema}.spans "
                "(id, document_id, entity_type, char_start, char_end, text_content, confidence) "
                "VALUES (:id, :doc_id, :entity_type, :char_start, :char_end, :text_val, "
                "        :confidence)"
            ),
            {
                "id": span_id,
                "doc_id": suggestion[1],
                "entity_type": suggestion[2],
                "char_start": suggestion[3],
                "char_end": suggestion[4],
                "text_val": suggestion[5],
                "confidence": float(suggestion[6]),
            },
        )
        connection.execute(
            text(
                f"INSERT INTO {schema}.span_batch_provenance "
                "(span_id, batch_id, acceptance_id) VALUES (:span_id, :batch_id, :acceptance_id)"
            ),
            {"span_id": span_id, "batch_id": batch_id, "acceptance_id": acceptance_id},
        )
        connection.execute(
            text(f"DELETE FROM {schema}.suggested_spans WHERE id = :id"),
            {"id": suggestion[0]},
        )
        promoted += 1

    connection.execute(
        text(
            "INSERT INTO public.notifications "
            "(id, tenant_id, recipient_role, recipient_user_id, kind, title, body, "
            " resource_type, resource_id) "
            "VALUES (:id, :tenant_id, 'tenant_admin', NULL, 'automated_batch_approved', "
            "        'Automated batch approved', :body, 'prelabel_batch', :batch_id)"
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "body": (
                f"Automated batch {batch_id} finished pre-labeling and its {promoted} spans "
                "were promoted directly to training data — no review was required."
            ),
            "batch_id": batch_id,
        },
    )

    return promoted


def run_prelabel_batch_sync(
    tenant_id: str, batch_id: str, llm_client=None, guidance_text: str = ""
) -> dict:
    """Pre-label every document in a batch, one at a time, on this worker.

    One job over N documents rather than N jobs, because the requirement is a single trackable
    unit with per-document outcomes (design.md Decision 2). Each document goes through
    `extract_and_ground_document` — change 1's pipeline, not a batch-flavoured variant of it —
    and its outcome is written in the same transaction as its spans.

    The broad `except Exception` is load-bearing: a batch is 100-200 documents and the spec
    requires that one bad document costs one document. A provider error, a malformed response, a
    document whose text went missing between enqueue and execution — each is one row marked
    `failed` with the reason on it, and the loop continues. The batch itself fails only if the
    loop cannot run at all.

    Queue: this task is registered on `annotation_service`'s Celery app, whose default queue is
    `settings.annotation_llm_celery_queue` — change 1's non-GPU queue. It carries no node-pool
    selector and never touches `training.jobs`; LLM calls are network I/O and have no business
    scaling a GPU pool (ADR-006, verification.md Risk 7).
    """
    schema = _schema(tenant_id)
    client = llm_client if llm_client is not None else get_llm_client()
    engine = _get_sync_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                f"UPDATE {schema}.prelabel_batches "
                "SET status = 'running', state = 'processing' WHERE id = :id"
            ),
            {"id": batch_id},
        )
        batch_kind = connection.execute(
            text(f"SELECT batch_kind FROM {schema}.prelabel_batches WHERE id = :id"),
            {"id": batch_id},
        ).scalar()
        doc_ids = [
            row[0]
            for row in connection.execute(
                text(
                    f"SELECT document_id FROM {schema}.prelabel_batch_documents "
                    "WHERE batch_id = :batch_id ORDER BY position"
                ),
                {"batch_id": batch_id},
            ).fetchall()
        ]

    succeeded = 0
    failed = 0
    for doc_id in doc_ids:
        try:
            result = extract_and_ground_document(
                engine, tenant_id, doc_id, client, guidance_text=guidance_text
            )
        except Exception as exc:  # noqa: BLE001 - see docstring: one document, one failure
            failed += 1
            with engine.begin() as connection:
                _mark_batch_document(
                    connection, schema, batch_id, doc_id, "failed", error=str(exc)
                )
            continue

        succeeded += 1
        with engine.begin() as connection:
            replace_suggested_spans(connection, schema, doc_id, result.spans)
            _mark_batch_document(
                connection, schema, batch_id, doc_id, "succeeded", counts=result.counts()
            )

    # The worker's `status` stays `completed` whenever the loop ran to the end; `state` is
    # the finer-grained lifecycle the portal renders (design.md Decision 3).
    if doc_ids and succeeded and failed:
        state = "partially_completed"
    elif doc_ids and failed and not succeeded:
        state = "failed"
    else:
        state = "completed"

    promoted = 0
    with engine.begin() as connection:
        connection.execute(
            text(
                f"UPDATE {schema}.prelabel_batches "
                "SET status = 'completed', state = :state, completed_at = :now WHERE id = :id"
            ),
            {"id": batch_id, "state": state, "now": _now()},
        )
        # `large` batches are never reviewed by anyone — the moment pre-labeling finishes, its
        # output *is* the training data (annotation-workflow-review-simplification design.md
        # Decision 1). `initial` batches still go to an Annotator Admin's acceptance review.
        if batch_kind == "large" and succeeded:
            promoted = _auto_promote_large_batch(connection, schema, tenant_id, batch_id)

    return {
        "documents": len(doc_ids),
        "succeeded": succeeded,
        "failed": failed,
        "state": state,
        "promoted": promoted,
    }


@celery_app.task(bind=True, name="run_prelabel_batch", max_retries=0)
def run_prelabel_batch(self, tenant_id: str, batch_id: str, guidance_text: str = ""):
    return run_prelabel_batch_sync(tenant_id, batch_id, guidance_text=guidance_text)


# --------------------------------------------------------------------------- LLM review route
#
# The LLM half of confidence-routed review. It resolves queued low-confidence predictions
# through `review_resolution.resolve_prediction` — the same function the human review endpoint
# calls, and the only thing in this change that writes a span (design.md Decision 4).
#
# Written async, unlike the pre-labeling job above, because `resolve_prediction` is async: the
# human endpoint that also calls it runs on an async session. The Celery task is a thin
# `asyncio.run` wrapper around it. A synchronous twin of the resolution path, written for this
# worker's convenience, would be a second span-writing path — exactly the divergence Decision 4
# exists to prevent — so the mismatch is absorbed here, at the caller.
#
# Nothing below writes to the span table. A span exists because an outcome was recorded and
# `create_span_from_outcome` made one from it, whoever reviewed.
#
# Nothing below creates, enqueues, or schedules a training job.


async def _tenant_review_policy(session, tenant_id: str) -> str:
    """This tenant's route, falling back to the configured default.

    Read from `public.tenants.review_policy`. A tenant with no row, or one carrying a value
    outside the vocabulary, falls back through `resolve_review_policy` — whose failure mode is
    "a person reviews it", never "the LLM reviews it" (design.md Decision 10).
    """
    result = await session.execute(
        text("SELECT review_policy FROM public.tenants WHERE id = :tid"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    return resolve_review_policy(row[0] if row else None, settings.default_review_policy)


async def _load_queued_predictions(session, schema: str, limit: int | None) -> list[dict]:
    """Queued predictions, oldest first, with the document text each one needs.

    The text is joined in rather than fetched per prediction: a queue is frequently many
    predictions over few documents, and one read per row would dominate the job.
    """
    sql = (
        f"SELECT p.id, p.document_id, p.entity_type, p.value, p.confidence, p.char_start, "
        f"       p.char_end, p.model_version, p.served_by_base_model, t.text "
        f"FROM {schema}.routed_predictions p "
        f"LEFT JOIN {schema}.document_text_spans t ON t.document_id = p.document_id "
        "WHERE p.disposition = 'queued' "
        "ORDER BY p.created_at ASC, p.id ASC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    result = await session.execute(text(sql))
    return [
        {
            "id": row[0],
            "document_id": row[1],
            "entity_type": row[2],
            "value": row[3],
            "confidence": row[4],
            "char_start": row[5],
            "char_end": row[6],
            "model_version": row[7],
            "served_by_base_model": row[8],
            "document_text": row[9] or "",
        }
        for row in result.fetchall()
    ]


async def run_llm_review_async(tenant_id: str, limit: int | None = None, llm_client=None) -> dict:
    """Review this tenant's queued predictions with the LLM.

    Returns counts rather than raising on a per-prediction failure: one prediction the provider
    could not answer for must not abandon the rest of the queue, and such a prediction is simply
    still queued — a correct state, not a lost one.

    A tenant whose policy is not `llm` is skipped without a provider call. That is Decision 10
    shipped: the route is implemented and tested but enabled for nobody until human-route
    agreement data exists to compare it against.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    schema = _schema(tenant_id)
    engine = create_async_engine(settings.database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            policy = await _tenant_review_policy(session, tenant_id)
            if policy != ROUTE_LLM:
                return {"skipped": True, "policy": policy, "reviewed": 0, "failed": 0}

            predictions = await _load_queued_predictions(session, schema, limit)
            if not predictions:
                return {"skipped": False, "policy": policy, "reviewed": 0, "failed": 0}

            entity_types = [
                item["name"] for item in await load_active_entity_config(session, tenant_id)
            ]
            client = llm_client if llm_client is not None else get_llm_client()

            reviewed = 0
            failed = 0
            for prediction in predictions:
                try:
                    body = review_prediction(
                        client, prediction, prediction["document_text"], entity_types
                    )
                except (LLMReviewError, LLMUnavailable) as exc:
                    # Left queued. A prediction the provider could not answer for has not been
                    # reviewed, and recording an outcome would claim otherwise.
                    failed += 1
                    print(
                        f"LLM_REVIEW_WARN tenant={tenant_id} prediction={prediction['id']} "
                        f"unresolved: {exc}",
                        flush=True,
                    )
                    continue

                await resolve_prediction(
                    session,
                    schema,
                    prediction,
                    body,
                    "annotation-llm-worker",
                    prediction["document_text"],
                    origin=ORIGIN_QUEUE,
                )
                reviewed += 1

            await session.commit()
            return {
                "skipped": False,
                "policy": policy,
                "reviewed": reviewed,
                "failed": failed,
            }
    finally:
        await engine.dispose()


def run_llm_review_sync(tenant_id: str, limit: int | None = None, llm_client=None) -> dict:
    """Synchronous entry point for the Celery worker, which has no running event loop."""
    return asyncio.run(run_llm_review_async(tenant_id, limit, llm_client))


@celery_app.task(bind=True, name="run_llm_review", max_retries=0)
def run_llm_review(self, tenant_id: str, limit: int | None = None):
    """Queue: registered on `annotation_service`'s Celery app, whose default queue is
    `settings.annotation_llm_celery_queue` — change 1's non-GPU queue. It carries no node-pool
    selector and never touches `training.jobs`; an LLM call is network I/O and has no business
    scaling a GPU pool (ADR-006, verification.md Risk 7)."""
    return run_llm_review_sync(tenant_id, limit)
