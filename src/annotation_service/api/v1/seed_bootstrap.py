"""Schema proposal, batch pre-labeling, and the sampled acceptance gate.

The path from a seed set to a first trained model. Three surfaces that share a service and a
tenant schema but nothing else:

  * `/schema-proposals` derives candidate entity types from a handful of documents. A candidate
    is a suggestion; approving one calls the entity-config API, which is the only thing in this
    system that creates an entity type (design.md Decision 1).
  * `/prelabel-batches` pre-labels a document set as one trackable job, replacing the browser
    loop change 2 deferred.
  * `/prelabel-batches/{id}/acceptance` is the gate between a batch of machine annotations and
    the training set: a random sample, a measured agreement rate, and one decision for the whole
    batch (design.md Decisions 3 and 4).

Everything here resolves the tenant schema the way every other `annotation_service` endpoint
does, and every statement is scoped to it (ADR-001).
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.annotation_service.api.v1.spans import generate_uuid, get_session, get_tenant_id
from src.annotation_service.api.v1._rbac import (
    ANNOTATOR,
    TENANT_ADMIN,
    require_roles,
    require_tenant_admin,
)
from src.annotation_service.celery_app import celery_app
from src.annotation_service.services.batch_acceptance import (
    DISPOSITIONS,
    agreement_rate,
    draw_sample,
)
from src.annotation_service.services.notify import notify
from src.shared.config import settings
from src.shared.entity_config_version import load_active_entity_config
from src.shared.exceptions import NotFoundError

router = APIRouter(tags=["seed-bootstrap"])

# `initial` batches validate the model on a handful of documents and are reviewed by the
# Tenant Admin; `large` batches are the main run and are reviewed by an Annotator Admin,
# whose acceptance is the final annotation gate (design.md Decision 2).
BATCH_KIND_INITIAL = "initial"
BATCH_KIND_LARGE = "large"
INITIAL_BATCH_MAX_DOCS = 5


def _derive_batch_state(batch_status: str, outcomes: list[dict]) -> str:
    """The named lifecycle the portal renders, derived from per-document outcomes.

    `prelabel_batches.status` stays the worker's job status; `state` adds the
    `partially_completed` distinction and the `processing` label (design.md Decision 3).
    """
    if batch_status in ("queued", "pending"):
        return "queued"
    if batch_status == "running":
        return "processing"
    # Terminal worker status — classify by what the documents actually did.
    if not outcomes:
        return "failed" if batch_status == "failed" else "completed"
    succeeded = sum(1 for o in outcomes if o["status"] == "succeeded")
    failed = sum(1 for o in outcomes if o["status"] == "failed")
    pending = sum(1 for o in outcomes if o["status"] == "pending")
    if pending and not (succeeded or failed):
        return "processing"
    if succeeded and not failed:
        return "completed"
    if failed and not succeeded:
        return "failed"
    return "partially_completed"


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _now():
    return datetime.now(timezone.utc)


def _user_id(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


def _coerce_json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _document_ids(body: dict) -> list[str]:
    """The submitted document set, de-duplicated with its order preserved.

    Order matters downstream: `prelabel_batch_documents.position` records it so a drawn sample
    can be shown not to be the first N."""
    raw = body.get("document_ids")
    if not isinstance(raw, list) or not raw:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "document_ids is required"},
        )
    seen = set()
    ordered = []
    for value in raw:
        if isinstance(value, str) and value and value not in seen:
            seen.add(value)
            ordered.append(value)
    if not ordered:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "document_ids is required"},
        )
    return ordered


async def _documents_with_text(
    session: AsyncSession, schema: str, doc_ids: list[str]
) -> list[str]:
    """Which of the submitted documents actually have extracted text.

    Checked at request time rather than on the worker so a caller learns immediately that the
    request could never have succeeded, matching change 1's trigger endpoint.

    Q&A-pair documents (`purpose = 'qa_pair'`) are excluded here: they are guidance input to
    a proposal, not seed or batch material, and must not enter the seed set or a pre-label
    batch (verification.md Risk 6)."""
    result = await session.execute(
        text(
            f"SELECT DISTINCT s.document_id FROM {schema}.document_text_spans s "
            f"JOIN {schema}.documents d ON d.id = s.document_id "
            "WHERE s.document_id = ANY(:doc_ids) AND COALESCE(s.text, '') <> '' "
            "AND COALESCE(d.purpose, '') <> 'qa_pair'"
        ),
        {"doc_ids": doc_ids},
    )
    present = {row[0] for row in result.fetchall()}
    return [doc_id for doc_id in doc_ids if doc_id in present]


# ---------------------------------------------------------------------------
# Schema proposal
# ---------------------------------------------------------------------------


@router.post("/api/v1/schema-proposals", status_code=202)
async def request_schema_proposal(
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Enqueue a schema proposal over a seed set.

    Returns a handle, not a proposal: the provider call happens on the worker. The 422 is the
    one condition that can be decided here — a seed set with no readable text cannot produce
    candidates no matter how long it runs."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    doc_ids = _document_ids(body)

    readable = await _documents_with_text(session, schema, doc_ids)
    if not readable:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_PROCESSED_DOCUMENTS",
                "message": "No document in the seed set has extracted text",
            },
        )

    # Optional Q&A-pair document: uploaded separately through the ordinary document path as
    # `purpose = 'qa_pair'` and referenced here by id so the proposal's inputs are
    # reproducible (design.md Decision 1). Its text guides which entity types the model
    # proposes; examples still ground against the seed documents.
    qa_pair_document_id = body.get("qa_pair_document_id")
    if qa_pair_document_id:
        qa_row = await session.execute(
            text(
                f"SELECT d.purpose, "
                f"  EXISTS(SELECT 1 FROM {schema}.document_text_spans s "
                f"         WHERE s.document_id = d.id AND COALESCE(s.text, '') <> '') "
                f"FROM {schema}.documents d WHERE d.id = :id"
            ),
            {"id": qa_pair_document_id},
        )
        qa = qa_row.fetchone()
        if qa is None or qa[0] != "qa_pair":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_QA_PAIR_DOCUMENT",
                    "message": (
                        "qa_pair_document_id must reference a document uploaded with "
                        "purpose 'qa_pair' (supported types: PDF, DOC, DOCX, TXT)"
                    ),
                },
            )
        if not qa[1]:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "QA_PAIR_NOT_PROCESSED",
                    "message": "The Q&A-pair document has no extracted text yet",
                },
            )

    proposal_id = generate_uuid()
    await session.execute(
        text(
            f"INSERT INTO {schema}.schema_proposals "
            "(id, status, seed_document_ids, qa_pair_document_id, requested_by) "
            "VALUES (:id, 'queued', CAST(:seed AS JSONB), :qa_pair_document_id, :requested_by)"
        ),
        {
            "id": proposal_id,
            "seed": json.dumps(readable),
            "qa_pair_document_id": qa_pair_document_id,
            "requested_by": _user_id(request),
        },
    )
    await session.commit()

    celery_app.send_task(
        "run_schema_proposal",
        args=[tenant_id, proposal_id],
        queue=settings.annotation_llm_celery_queue,
    )

    return {
        "proposal_id": proposal_id,
        "status": "queued",
        "seed_document_count": len(readable),
        "qa_pair_document_id": qa_pair_document_id,
    }


@router.get("/api/v1/schema-proposals/{proposal_id}")
async def get_schema_proposal(
    proposal_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """The proposal and its candidates, each with its current disposition."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT id, status, seed_document_ids, error_message, created_at, completed_at, "
            f"       qa_pair_document_id "
            f"FROM {schema}.schema_proposals WHERE id = :id LIMIT 1"
        ),
        {"id": proposal_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("SchemaProposal", proposal_id)

    candidates = await session.execute(
        text(
            f"SELECT id, name, description, examples, disposition, created_entity_type "
            f"FROM {schema}.schema_proposal_candidates WHERE proposal_id = :id ORDER BY name"
        ),
        {"id": proposal_id},
    )

    return {
        "proposal_id": row[0],
        "status": row[1],
        "seed_document_ids": _coerce_json(row[2]) or [],
        "qa_pair_document_id": row[6],
        "error_message": row[3],
        "created_at": str(row[4]),
        "completed_at": str(row[5]) if row[5] else None,
        "candidates": [
            {
                "id": candidate[0],
                "name": candidate[1],
                "description": candidate[2],
                "examples": _coerce_json(candidate[3]) or [],
                "disposition": candidate[4],
                "created_entity_type": candidate[5],
            }
            for candidate in candidates.fetchall()
        ],
    }


async def _load_candidate(session: AsyncSession, schema: str, candidate_id: str):
    result = await session.execute(
        text(
            f"SELECT id, proposal_id, name, description, examples, disposition "
            f"FROM {schema}.schema_proposal_candidates WHERE id = :id LIMIT 1"
        ),
        {"id": candidate_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("SchemaProposalCandidate", candidate_id)
    return row


@router.patch("/api/v1/schema-proposals/candidates/{candidate_id}")
async def edit_candidate(
    candidate_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Edit a candidate's name, description, or examples before approving it.

    The disposition becomes `edited` rather than staying `pending`, so the record distinguishes
    a candidate a human accepted as written from one they rewrote — the proposal's value as
    evidence about the model depends on that difference being visible afterwards."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    row = await _load_candidate(session, schema, candidate_id)

    if row[5] in ("approved", "rejected"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CANDIDATE_DECIDED",
                "message": f"Candidate has already been {row[5]}",
            },
        )

    updates = ["disposition = 'edited'", "updated_at = :now"]
    params = {"id": candidate_id, "now": _now()}
    if "name" in body:
        updates.append("name = :name")
        params["name"] = body["name"]
    if "description" in body:
        updates.append("description = :description")
        params["description"] = body["description"]
    if "examples" in body:
        updates.append("examples = CAST(:examples AS JSONB)")
        params["examples"] = json.dumps(body["examples"] or [])

    await session.execute(
        text(
            f"UPDATE {schema}.schema_proposal_candidates SET {', '.join(updates)} WHERE id = :id"
        ),
        params,
    )
    await session.commit()

    row = await _load_candidate(session, schema, candidate_id)
    return {
        "id": row[0],
        "name": row[2],
        "description": row[3],
        "examples": _coerce_json(row[4]) or [],
        "disposition": row[5],
    }


@router.post("/api/v1/schema-proposals/candidates/{candidate_id}/approve", status_code=201)
async def approve_candidate(
    candidate_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Create the entity type this candidate describes.

    `EntityService.create_entity_type` is the same code the entity-config `POST /entity-types`
    endpoint runs; calling it is what makes this an approval rather than a second creation path.
    Nothing here writes `public.entity_definitions` — the validation, the `sql_identifier`
    assignment, the version, and the relational-projection reconcile all belong to that service
    and are inherited rather than reimplemented (design.md Decision 1, verification.md Risk 1).

    The duplicate-name check sits here rather than in `EntityService`: entity-config's create
    contract is unchanged by this change ("Modified Capabilities: None"), so the collision is
    rejected by the caller that knows it is a collision.
    """
    from src.gateway.services.entity_service import EntityService

    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    row = await _load_candidate(session, schema, candidate_id)

    if row[5] == "approved":
        raise HTTPException(
            status_code=422,
            detail={"code": "CANDIDATE_DECIDED", "message": "Candidate has already been approved"},
        )
    if row[5] == "rejected":
        raise HTTPException(
            status_code=422,
            detail={"code": "CANDIDATE_DECIDED", "message": "Candidate has already been rejected"},
        )

    name = row[2]
    existing = await session.execute(
        text(
            "SELECT id FROM public.entity_definitions "
            "WHERE tenant_id = :tid AND LOWER(name) = LOWER(:name) AND is_active = true LIMIT 1"
        ),
        {"tid": tenant_id, "name": name},
    )
    if existing.fetchone():
        raise HTTPException(
            status_code=422,
            detail={
                "code": "DUPLICATE_ENTITY_TYPE",
                "message": f"Entity type '{name}' already exists for this tenant",
            },
        )

    created = await EntityService(session).create_entity_type(
        tenant_id,
        {
            "name": name,
            "description": row[3],
            # The candidate's grounded quotes become the entity type's `examples`, which is what
            # the keyword pre-labeler matches on and what pre-labeling prompts show the model.
            # They are already known to appear verbatim in the tenant's own documents, which is
            # more than a hand-typed example can claim.
            "examples": _coerce_json(row[4]) or [],
            # Recorded so the Entity Types page can show where a type an admin does not
            # recognise came from (entity-type-provenance change).
            "provenance": "suggested",
        },
    )

    await session.execute(
        text(
            f"UPDATE {schema}.schema_proposal_candidates "
            "SET disposition = 'approved', created_entity_type = :name, updated_at = :now "
            "WHERE id = :id"
        ),
        {"id": candidate_id, "name": name, "now": _now()},
    )
    await session.commit()

    return {"candidate_id": candidate_id, "disposition": "approved", "entity_type": created}


@router.post("/api/v1/schema-proposals/candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Record that a candidate was rejected. Creates nothing."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    row = await _load_candidate(session, schema, candidate_id)

    if row[5] == "approved":
        raise HTTPException(
            status_code=422,
            detail={"code": "CANDIDATE_DECIDED", "message": "Candidate has already been approved"},
        )

    await session.execute(
        text(
            f"UPDATE {schema}.schema_proposal_candidates "
            "SET disposition = 'rejected', updated_at = :now WHERE id = :id"
        ),
        {"id": candidate_id, "now": _now()},
    )
    await session.commit()

    return {"candidate_id": candidate_id, "disposition": "rejected"}


# ---------------------------------------------------------------------------
# Batch pre-labeling
# ---------------------------------------------------------------------------


@router.post("/api/v1/prelabel-batches", status_code=202)
async def create_prelabel_batch(
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Enqueue one batch pre-labeling job over a document set.

    One `batch_id` for the whole set, whatever its size — the point of the endpoint. The
    per-document rows are written here, at submission, rather than by the worker, so the batch
    knows what it is supposed to cover even if the worker never starts."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    doc_ids = _document_ids(body)

    batch_kind = body.get("batch_kind", BATCH_KIND_LARGE)
    if batch_kind not in (BATCH_KIND_INITIAL, BATCH_KIND_LARGE):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_BATCH_KIND",
                "message": "batch_kind must be 'initial' or 'large'",
            },
        )

    readable = await _documents_with_text(session, schema, doc_ids)
    if not readable:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_PROCESSED_DOCUMENTS",
                "message": "No document in the batch has extracted text",
            },
        )

    if batch_kind == BATCH_KIND_INITIAL and len(readable) > INITIAL_BATCH_MAX_DOCS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INITIAL_BATCH_TOO_LARGE",
                "message": (
                    f"An initial validation batch covers at most {INITIAL_BATCH_MAX_DOCS} "
                    "documents"
                ),
            },
        )

    entity_types = await load_active_entity_config(session, tenant_id)
    if not entity_types:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_ENTITY_TYPES",
                "message": "No entity types are configured for this tenant",
            },
        )

    guidance_text = ""
    if batch_kind == BATCH_KIND_LARGE:
        guidance_text = render_guidance_text(
            await _latest_initial_guidance(session, schema)
        )

    batch_id = generate_uuid()
    await session.execute(
        text(
            f"INSERT INTO {schema}.prelabel_batches (id, status, batch_kind, state, requested_by) "
            "VALUES (:id, 'queued', :batch_kind, 'queued', :requested_by)"
        ),
        {"id": batch_id, "batch_kind": batch_kind, "requested_by": _user_id(request)},
    )
    for position, doc_id in enumerate(readable):
        await session.execute(
            text(
                f"INSERT INTO {schema}.prelabel_batch_documents "
                "(id, batch_id, document_id, position, status) "
                "VALUES (:id, :batch_id, :doc_id, :position, 'pending')"
            ),
            {
                "id": str(uuid.uuid4()),
                "batch_id": batch_id,
                "doc_id": doc_id,
                "position": position,
            },
        )
    await session.commit()

    celery_app.send_task(
        "run_prelabel_batch",
        # The reviewed initial batch's guidance, rendered as prompt text; empty for an
        # initial batch or when no initial batch has been reviewed.
        args=[tenant_id, batch_id, guidance_text],
        queue=settings.annotation_llm_celery_queue,
    )

    return {
        "batch_id": batch_id,
        "status": "queued",
        "state": "queued",
        "batch_kind": batch_kind,
        "document_count": len(readable),
        "guidance_applied": bool(guidance_text),
    }


@router.get("/api/v1/prelabel-batches")
async def list_prelabel_batches(
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Every batch for the tenant, newest first — the automated stepper reads this to
    decide which steps are done / ready / blocked. One row per batch, no per-document
    detail."""
    require_roles(request, TENANT_ADMIN, ANNOTATOR)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT b.id, b.status, b.state, b.batch_kind, b.annotator_review_status, "
            f"  b.training_eligible_at, b.created_at, "
            f"  (SELECT decision FROM {schema}.batch_acceptance_records r "
            f"   WHERE r.batch_id = b.id ORDER BY r.created_at DESC LIMIT 1) AS acceptance_decision "
            f"FROM {schema}.prelabel_batches b ORDER BY b.created_at DESC"
        )
    )
    return {
        "batches": [
            {
                "batch_id": r[0],
                "status": r[1],
                "state": r[2],
                "batch_kind": r[3],
                "annotator_review_status": r[4],
                "training_eligible_at": r[5].isoformat() if r[5] else None,
                "created_at": r[6].isoformat() if r[6] else None,
                "acceptance_decision": r[7],
            }
            for r in result.fetchall()
        ]
    }


@router.get("/api/v1/prelabel-batches/{batch_id}")
async def get_prelabel_batch(
    batch_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Aggregate batch status plus every document's own outcome.

    The aggregate is derived from the per-document rows rather than kept as a counter: a counter
    and the rows it counts can disagree, and the rows are the record."""
    require_roles(request, TENANT_ADMIN, ANNOTATOR)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT id, status, error_message, created_at, completed_at, batch_kind, state "
            f"FROM {schema}.prelabel_batches WHERE id = :id LIMIT 1"
        ),
        {"id": batch_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("PrelabelBatch", batch_id)

    documents = await session.execute(
        text(
            f"SELECT document_id, position, status, counts, error_message, completed_at "
            f"FROM {schema}.prelabel_batch_documents WHERE batch_id = :id ORDER BY position"
        ),
        {"id": batch_id},
    )
    document_rows = documents.fetchall()

    outcomes = [
        {
            "document_id": document[0],
            "position": document[1],
            "status": document[2],
            "counts": _coerce_json(document[3]) or {},
            "error_message": document[4],
            "completed_at": str(document[5]) if document[5] else None,
        }
        for document in document_rows
    ]

    batch_status = row[1]
    cached_state = row[6]
    state = cached_state or _derive_batch_state(batch_status, outcomes)

    # Reconcile-on-read (design.md Risks): a worker that died after the last document
    # outcome but before writing the terminal state would otherwise read `processing`
    # forever. If the job is terminal and every document has an outcome, cache it now.
    terminal = batch_status in ("completed", "failed")
    all_settled = outcomes and all(o["status"] != "pending" for o in outcomes)
    if cached_state is None and terminal and all_settled:
        await session.execute(
            text(f"UPDATE {schema}.prelabel_batches SET state = :state WHERE id = :id"),
            {"state": state, "id": batch_id},
        )
        await session.commit()

    succeeded = sum(1 for outcome in outcomes if outcome["status"] == "succeeded")
    return {
        "batch_id": row[0],
        "status": batch_status,
        "state": state,
        "batch_kind": row[5],
        "error_message": row[2],
        "created_at": str(row[3]),
        "completed_at": str(row[4]) if row[4] else None,
        "document_count": len(outcomes),
        "progress": {"settled": sum(1 for o in outcomes if o["status"] != "pending"), "total": len(outcomes)},
        "succeeded": succeeded,
        "failed": sum(1 for outcome in outcomes if outcome["status"] == "failed"),
        "pending": sum(1 for outcome in outcomes if outcome["status"] == "pending"),
        "ungrounded": sum(
            int(outcome["counts"].get("ungrounded") or 0) for outcome in outcomes
        ),
        "documents": outcomes,
    }


@router.post("/api/v1/prelabel-batches/{batch_id}/guidance", status_code=201)
async def record_initial_batch_guidance(
    batch_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """A Tenant Admin's corrections and note from reviewing one document of an `initial`
    batch. Stored per (batch, document) and folded into the prompt when the subsequent
    `large` batch runs (design.md Decision 5). Repeated calls for the same document
    replace the previous guidance."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    batch = await _load_batch(session, schema, batch_id)
    if batch[2] != BATCH_KIND_INITIAL:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NOT_AN_INITIAL_BATCH",
                "message": "Review guidance is only recorded for initial validation batches",
            },
        )

    document_id = body.get("document_id")
    if not document_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "document_id is required"},
        )
    corrected_spans = body.get("corrected_spans") or []
    note = body.get("note")

    await session.execute(
        text(
            f"INSERT INTO {schema}.prelabel_batch_guidance "
            "(id, batch_id, document_id, corrected_spans, note) "
            "VALUES (:id, :batch_id, :doc_id, CAST(:spans AS JSONB), :note) "
            "ON CONFLICT (batch_id, document_id) DO UPDATE "
            "SET corrected_spans = EXCLUDED.corrected_spans, note = EXCLUDED.note"
        ),
        {
            "id": generate_uuid(),
            "batch_id": batch_id,
            "doc_id": document_id,
            "spans": json.dumps(corrected_spans),
            "note": note,
        },
    )
    await session.commit()
    return {"batch_id": batch_id, "document_id": document_id, "recorded": True}


# ---------------------------------------------------------------------------
# Sampled acceptance gate
# ---------------------------------------------------------------------------


async def _batch_document_ids(session: AsyncSession, schema: str, batch_id: str) -> list[str]:
    result = await session.execute(
        text(
            f"SELECT document_id FROM {schema}.prelabel_batch_documents "
            "WHERE batch_id = :id ORDER BY position"
        ),
        {"id": batch_id},
    )
    return [row[0] for row in result.fetchall()]


async def _load_batch(session: AsyncSession, schema: str, batch_id: str):
    result = await session.execute(
        text(
            f"SELECT id, status, batch_kind, annotator_review_status, training_eligible_at "
            f"FROM {schema}.prelabel_batches WHERE id = :id LIMIT 1"
        ),
        {"id": batch_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("PrelabelBatch", batch_id)
    return row


def _gate_acceptance_reviewer(request: Request, batch_kind: str) -> None:
    """An `initial` batch is validated by the Tenant Admin; a `large` batch's acceptance
    review is the Annotator Admin's final annotation gate (design.md Decision 2)."""
    if batch_kind == BATCH_KIND_INITIAL:
        require_roles(request, TENANT_ADMIN)
    else:
        require_roles(request, ANNOTATOR)


async def _latest_initial_guidance(session: AsyncSession, schema: str) -> list[dict]:
    """Corrections and notes from the most recent `initial` batch that has any guidance,
    rendered for the `large`-batch prompt. Empty when no initial batch has been reviewed."""
    batch = await session.execute(
        text(
            f"SELECT b.id FROM {schema}.prelabel_batches b "
            f"WHERE b.batch_kind = 'initial' "
            f"  AND EXISTS (SELECT 1 FROM {schema}.prelabel_batch_guidance g "
            f"             WHERE g.batch_id = b.id) "
            "ORDER BY b.created_at DESC LIMIT 1"
        )
    )
    batch_row = batch.fetchone()
    if not batch_row:
        return []
    rows = await session.execute(
        text(
            f"SELECT document_id, corrected_spans, note "
            f"FROM {schema}.prelabel_batch_guidance WHERE batch_id = :id"
        ),
        {"id": batch_row[0]},
    )
    return [
        {"document_id": r[0], "corrected_spans": _coerce_json(r[1]) or [], "note": r[2]}
        for r in rows.fetchall()
    ]


def render_guidance_text(guidance: list[dict]) -> str:
    """Reviewer guidance from an initial batch, as a prompt section. Corrected spans become
    `"<quote>" -> <type>` lines; notes are included verbatim (design.md Decision 5)."""
    if not guidance:
        return ""
    lines: list[str] = []
    for entry in guidance:
        for span in entry.get("corrected_spans") or []:
            quote = (span or {}).get("text") or (span or {}).get("quote")
            entity_type = (span or {}).get("entity_type") or (span or {}).get("type")
            if quote and entity_type:
                lines.append(f'  "{quote}" -> {entity_type}')
        note = (entry.get("note") or "").strip()
        if note:
            lines.append(f"  note: {note}")
    if not lines:
        return ""
    return (
        "Reviewer guidance from validation on a sample of these documents. Apply it when it "
        "helps; it does not limit which entity types or how many occurrences you extract.\n"
        + "\n".join(lines)
        + "\n\n"
    )


async def _latest_acceptance(session: AsyncSession, schema: str, batch_id: str):
    result = await session.execute(
        text(
            f"SELECT id, sampled_document_ids, sample_size, sampled, agreement_threshold, "
            f"       agreement_rate, reviewed_count, agreed_count, dispositions, decision, "
            f"       reviewer, created_at, decided_at "
            f"FROM {schema}.batch_acceptance_records WHERE batch_id = :id "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"id": batch_id},
    )
    return result.fetchone()


def _acceptance_body(row) -> dict:
    return {
        "acceptance_id": row[0],
        "sampled_document_ids": _coerce_json(row[1]) or [],
        "sample_size": row[2],
        "sampled": row[3],
        "agreement_threshold": row[4],
        "agreement_rate": row[5],
        "reviewed_count": row[6],
        "agreed_count": row[7],
        "dispositions": _coerce_json(row[8]) or [],
        "decision": row[9],
        "reviewer": row[10],
        "created_at": str(row[11]),
        "decided_at": str(row[12]) if row[12] else None,
    }


@router.post("/api/v1/prelabel-batches/{batch_id}/acceptance", status_code=201)
async def start_acceptance_review(
    batch_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Draw the review sample and open an acceptance record.

    The drawn ids are written here, at selection time, and never recomputed. That is what makes
    the rate recorded against them auditable: a sample re-derived at read time could be a
    different sample, and a rate measured against an unknown set is a number nobody can check
    (design.md Decision 4).

    A batch already rejected does not get a fresh sample. Re-drawing until a sample happens to
    pass is precisely the failure the gate exists to prevent, and it is the reason retaining a
    rejected batch's suggestions is safe (design.md, task 1.5).
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    batch = await _load_batch(session, schema, batch_id)
    _gate_acceptance_reviewer(request, batch[2])

    existing = await _latest_acceptance(session, schema, batch_id)
    if existing is not None and existing[9] in ("accepted", "rejected"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "BATCH_ALREADY_DECIDED",
                "message": f"Batch acceptance has already been {existing[9]}",
            },
        )
    if existing is not None:
        return _acceptance_body(existing)

    document_ids = await _batch_document_ids(session, schema, batch_id)
    if not document_ids:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_BATCH", "message": "Batch contains no documents"},
        )

    sampled = draw_sample(
        document_ids,
        settings.seed_bootstrap_sample_size,
        settings.seed_bootstrap_sampling_enabled,
    )

    acceptance_id = generate_uuid()
    await session.execute(
        text(
            f"INSERT INTO {schema}.batch_acceptance_records "
            "(id, batch_id, sampled_document_ids, sample_size, sampled, agreement_threshold, "
            " decision, reviewer) "
            "VALUES (:id, :batch_id, CAST(:sampled_ids AS JSONB), :sample_size, :sampled, "
            "        :threshold, 'in_review', :reviewer)"
        ),
        {
            "id": acceptance_id,
            "batch_id": batch_id,
            "sampled_ids": json.dumps(sampled),
            "sample_size": len(sampled),
            # Recorded per record rather than read back from configuration: a rate measured
            # under full review and one measured under sampling are not the same evidence, and
            # configuration changes.
            "sampled": settings.seed_bootstrap_sampling_enabled
            and len(sampled) < len(document_ids),
            "threshold": settings.seed_bootstrap_agreement_threshold,
            "reviewer": _user_id(request),
        },
    )
    await session.commit()

    row = await _latest_acceptance(session, schema, batch_id)
    return _acceptance_body(row)


@router.get("/api/v1/prelabel-batches/{batch_id}/acceptance")
async def get_acceptance_review(
    batch_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """The acceptance record, the drawn sample, and the suggestions awaiting a disposition."""
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    batch = await _load_batch(session, schema, batch_id)
    _gate_acceptance_reviewer(request, batch[2])

    row = await _latest_acceptance(session, schema, batch_id)
    if row is None:
        raise NotFoundError("BatchAcceptanceRecord", batch_id)

    body = _acceptance_body(row)
    suggestions = await session.execute(
        text(
            f"SELECT id, document_id, entity_type, char_start, char_end, text_content, "
            f"       confidence, source FROM {schema}.suggested_spans "
            "WHERE document_id = ANY(:doc_ids) ORDER BY document_id, char_start"
        ),
        {"doc_ids": body["sampled_document_ids"]},
    )
    body["suggestions"] = [
        {
            "id": suggestion[0],
            "document_id": suggestion[1],
            "entity_type": suggestion[2],
            "char_start": suggestion[3],
            "char_end": suggestion[4],
            "text": suggestion[5],
            "confidence": float(suggestion[6]),
            "source": suggestion[7],
        }
        for suggestion in suggestions.fetchall()
    ]
    return body


async def _sample_suggestion_ids(
    session: AsyncSession, schema: str, sampled_document_ids: list[str]
) -> set[str]:
    result = await session.execute(
        text(
            f"SELECT id FROM {schema}.suggested_spans WHERE document_id = ANY(:doc_ids)"
        ),
        {"doc_ids": sampled_document_ids},
    )
    return {row[0] for row in result.fetchall()}


@router.post("/api/v1/prelabel-batches/{batch_id}/acceptance/review")
async def submit_acceptance_review(
    batch_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Record the reviewer's dispositions and compute the agreement rate.

    Measuring and deciding are separate requests on purpose: the reviewer sees the rate their
    own review produced before anything is promoted, and a rate below the threshold is recorded
    whether or not they then try to accept (the spec requires the measurement to survive the
    refusal).
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    batch = await _load_batch(session, schema, batch_id)
    _gate_acceptance_reviewer(request, batch[2])

    row = await _latest_acceptance(session, schema, batch_id)
    if row is None:
        raise NotFoundError("BatchAcceptanceRecord", batch_id)
    if row[9] in ("accepted", "rejected"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "BATCH_ALREADY_DECIDED",
                "message": f"Batch acceptance has already been {row[9]}",
            },
        )

    submitted = body.get("dispositions")
    if not isinstance(submitted, list):
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "dispositions is required"},
        )

    sampled_ids = _coerce_json(row[1]) or []
    expected = await _sample_suggestion_ids(session, schema, sampled_ids)

    # Keyed by suggestion id, so a client that sends the same suggestion twice contributes one
    # disposition rather than two. Without this, repeating an `agree` would raise the measured
    # rate without any additional review having happened — a way to talk the gate up that has
    # nothing to do with the batch's quality. Last write wins, which is what a reviewer changing
    # their mind mid-submission means.
    by_suggestion: dict[str, str] = {}
    for element in submitted:
        if not isinstance(element, dict):
            continue
        suggestion_id = element.get("suggestion_id")
        disposition = element.get("disposition")
        if suggestion_id not in expected:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": f"Suggestion '{suggestion_id}' is not in the drawn sample",
                },
            )
        if disposition not in DISPOSITIONS:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": f"disposition must be one of {list(DISPOSITIONS)}",
                },
            )
        by_suggestion[suggestion_id] = disposition

    cleaned = [
        {"suggestion_id": suggestion_id, "disposition": disposition}
        for suggestion_id, disposition in by_suggestion.items()
    ]
    agreed, reviewed, rate = agreement_rate(cleaned)
    complete = set(by_suggestion) == expected

    await session.execute(
        text(
            f"UPDATE {schema}.batch_acceptance_records "
            "SET dispositions = CAST(:dispositions AS JSONB), agreement_rate = :rate, "
            "    reviewed_count = :reviewed, agreed_count = :agreed, reviewer = :reviewer "
            "WHERE id = :id"
        ),
        {
            "id": row[0],
            "dispositions": json.dumps(cleaned),
            "rate": rate,
            "reviewed": reviewed,
            "agreed": agreed,
            "reviewer": _user_id(request),
        },
    )
    await session.commit()

    return {
        "acceptance_id": row[0],
        "reviewed_count": reviewed,
        "agreed_count": agreed,
        "agreement_rate": rate,
        "agreement_threshold": row[4],
        "sample_review_complete": complete,
        "expected_count": len(expected),
        "meets_threshold": rate is not None and rate >= row[4],
    }


@router.post("/api/v1/prelabel-batches/{batch_id}/acceptance/accept")
async def accept_batch(
    batch_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Promote every suggestion in the batch, or promote nothing.

    Three refusals, in order, and none of them promotes a partial batch:

      * the sample review is not finished, so there is no measurement to gate on;
      * the batch was already decided — an accepted batch is not re-promoted, and a rejected one
        never becomes acceptable (task 1.5);
      * the measured rate is below the threshold, which records the rejection and promotes zero
        spans. There is deliberately no branch here that promotes the reviewed documents and
        leaves the rest, because a dataset that silently mixes verified and unverified labels
        cannot be separated again afterwards (design.md Decision 3, verification.md Risk 4).

    A sub-threshold batch keeps its suggestions. They stay available through the ordinary
    per-document promote endpoint, so the LLM spend is salvageable by hand; what is closed is
    the bulk route, permanently.
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    batch = await _load_batch(session, schema, batch_id)
    batch_kind = batch[2]
    _gate_acceptance_reviewer(request, batch_kind)

    row = await _latest_acceptance(session, schema, batch_id)
    if row is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SAMPLE_REVIEW_INCOMPLETE",
                "message": "No acceptance review has been started for this batch",
            },
        )
    if row[9] in ("accepted", "rejected"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "BATCH_ALREADY_DECIDED",
                "message": f"Batch acceptance has already been {row[9]}",
            },
        )

    acceptance_id = row[0]
    sampled_ids = _coerce_json(row[1]) or []
    threshold = row[4]
    dispositions = _coerce_json(row[8]) or []

    expected = await _sample_suggestion_ids(session, schema, sampled_ids)
    reviewed_ids = {element.get("suggestion_id") for element in dispositions}
    if not expected or reviewed_ids != expected:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SAMPLE_REVIEW_INCOMPLETE",
                "message": (
                    "Every suggestion in the drawn sample must have a disposition before the "
                    "batch can be accepted"
                ),
            },
        )

    agreed, reviewed, rate = agreement_rate(dispositions)
    if rate is None or rate < threshold:
        await session.execute(
            text(
                f"UPDATE {schema}.batch_acceptance_records "
                "SET decision = 'rejected', agreement_rate = :rate, reviewed_count = :reviewed, "
                "    agreed_count = :agreed, reviewer = :reviewer, decided_at = :now "
                "WHERE id = :id"
            ),
            {
                "id": acceptance_id,
                "rate": rate,
                "reviewed": reviewed,
                "agreed": agreed,
                "reviewer": _user_id(request),
                "now": _now(),
            },
        )
        await session.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AGREEMENT_BELOW_THRESHOLD",
                "message": (
                    f"Measured agreement rate {rate} is below the configured threshold "
                    f"{threshold}; no spans were promoted"
                ),
                "agreement_rate": rate,
                "agreement_threshold": threshold,
            },
        )

    document_ids = await _batch_document_ids(session, schema, batch_id)
    suggestions = await session.execute(
        text(
            f"SELECT id, document_id, entity_type, char_start, char_end, text_content, "
            f"       confidence FROM {schema}.suggested_spans "
            "WHERE document_id = ANY(:doc_ids) ORDER BY document_id, char_start"
        ),
        {"doc_ids": document_ids},
    )

    promoted = 0
    for suggestion in suggestions.fetchall():
        span_id = generate_uuid()
        # The same INSERT `promote_suggested_span` performs, column for column. A bulk-promoted
        # span must be an ordinary confirmed span — the provenance below is what distinguishes
        # it, not a different shape of row.
        await session.execute(
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
        await session.execute(
            text(
                f"INSERT INTO {schema}.span_batch_provenance "
                "(span_id, batch_id, acceptance_id) VALUES (:span_id, :batch_id, :acceptance_id)"
            ),
            {"span_id": span_id, "batch_id": batch_id, "acceptance_id": acceptance_id},
        )
        await session.execute(
            text(f"DELETE FROM {schema}.suggested_spans WHERE id = :id"),
            {"id": suggestion[0]},
        )
        promoted += 1

    await session.execute(
        text(
            f"UPDATE {schema}.batch_acceptance_records "
            "SET decision = 'accepted', agreement_rate = :rate, reviewed_count = :reviewed, "
            "    agreed_count = :agreed, reviewer = :reviewer, decided_at = :now "
            "WHERE id = :id"
        ),
        {
            "id": acceptance_id,
            "rate": rate,
            "reviewed": reviewed,
            "agreed": agreed,
            "reviewer": _user_id(request),
            "now": _now(),
        },
    )

    # A `large` batch an Annotator Admin accepts is the final annotation gate: the batch
    # becomes training-eligible and the Tenant Admin is notified — no second Tenant Admin
    # review (design.md Decisions 2 and 6). The conditional UPDATE + guarded notify make
    # the transition fire exactly once even if `accept` is retried (ADR-011).
    training_eligible = False
    if batch_kind == BATCH_KIND_LARGE:
        eligible_result = await session.execute(
            text(
                f"UPDATE {schema}.prelabel_batches "
                "SET training_eligible_at = NOW(), annotator_review_status = 'approved' "
                "WHERE id = :id AND training_eligible_at IS NULL"
            ),
            {"id": batch_id},
        )
        if eligible_result.rowcount:
            training_eligible = True
            await notify(
                session,
                tenant_id=tenant_id,
                kind="automated_batch_approved",
                title="Automated batch approved",
                body=(
                    f"An annotator has reviewed and approved automated batch {batch_id}. "
                    f"The {promoted} confirmed spans are now eligible for model training."
                ),
                resource_type="prelabel_batch",
                resource_id=batch_id,
            )

    await session.commit()

    return {
        "acceptance_id": acceptance_id,
        "batch_id": batch_id,
        "batch_kind": batch_kind,
        "decision": "accepted",
        "agreement_rate": rate,
        "agreement_threshold": threshold,
        "sample_size": row[2],
        "promoted_spans": promoted,
        "training_eligible": training_eligible,
    }
