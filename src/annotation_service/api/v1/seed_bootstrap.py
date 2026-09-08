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
from src.annotation_service.celery_app import celery_app
from src.annotation_service.services.batch_acceptance import (
    DISPOSITIONS,
    agreement_rate,
    draw_sample,
)
from src.shared.config import settings
from src.shared.entity_config_version import load_active_entity_config
from src.shared.exceptions import NotFoundError

router = APIRouter(tags=["seed-bootstrap"])


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
    request could never have succeeded, matching change 1's trigger endpoint."""
    result = await session.execute(
        text(
            f"SELECT DISTINCT document_id FROM {schema}.document_text_spans "
            "WHERE document_id = ANY(:doc_ids) AND COALESCE(text, '') <> ''"
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

    proposal_id = generate_uuid()
    await session.execute(
        text(
            f"INSERT INTO {schema}.schema_proposals "
            "(id, status, seed_document_ids, requested_by) "
            "VALUES (:id, 'queued', CAST(:seed AS JSONB), :requested_by)"
        ),
        {"id": proposal_id, "seed": json.dumps(readable), "requested_by": _user_id(request)},
    )
    await session.commit()

    celery_app.send_task(
        "run_schema_proposal",
        args=[tenant_id, proposal_id],
        queue=settings.annotation_llm_celery_queue,
    )

    return {"proposal_id": proposal_id, "status": "queued", "seed_document_count": len(readable)}


@router.get("/api/v1/schema-proposals/{proposal_id}")
async def get_schema_proposal(
    proposal_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """The proposal and its candidates, each with its current disposition."""
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT id, status, seed_document_ids, error_message, created_at, completed_at "
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
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    doc_ids = _document_ids(body)

    readable = await _documents_with_text(session, schema, doc_ids)
    if not readable:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_PROCESSED_DOCUMENTS",
                "message": "No document in the batch has extracted text",
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

    batch_id = generate_uuid()
    await session.execute(
        text(
            f"INSERT INTO {schema}.prelabel_batches (id, status, requested_by) "
            "VALUES (:id, 'queued', :requested_by)"
        ),
        {"id": batch_id, "requested_by": _user_id(request)},
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
        args=[tenant_id, batch_id],
        queue=settings.annotation_llm_celery_queue,
    )

    return {"batch_id": batch_id, "status": "queued", "document_count": len(readable)}


@router.get("/api/v1/prelabel-batches/{batch_id}")
async def get_prelabel_batch(
    batch_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Aggregate batch status plus every document's own outcome.

    The aggregate is derived from the per-document rows rather than kept as a counter: a counter
    and the rows it counts can disagree, and the rows are the record."""
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT id, status, error_message, created_at, completed_at "
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

    return {
        "batch_id": row[0],
        "status": row[1],
        "error_message": row[2],
        "created_at": str(row[3]),
        "completed_at": str(row[4]) if row[4] else None,
        "document_count": len(outcomes),
        "succeeded": sum(1 for outcome in outcomes if outcome["status"] == "succeeded"),
        "failed": sum(1 for outcome in outcomes if outcome["status"] == "failed"),
        "pending": sum(1 for outcome in outcomes if outcome["status"] == "pending"),
        "ungrounded": sum(
            int(outcome["counts"].get("ungrounded") or 0) for outcome in outcomes
        ),
        "documents": outcomes,
    }


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
        text(f"SELECT id, status FROM {schema}.prelabel_batches WHERE id = :id LIMIT 1"),
        {"id": batch_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("PrelabelBatch", batch_id)
    return row


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
    await _load_batch(session, schema, batch_id)

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
    await _load_batch(session, schema, batch_id)

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
    await _load_batch(session, schema, batch_id)

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
    await _load_batch(session, schema, batch_id)

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
    await session.commit()

    return {
        "acceptance_id": acceptance_id,
        "batch_id": batch_id,
        "decision": "accepted",
        "agreement_rate": rate,
        "agreement_threshold": threshold,
        "sample_size": row[2],
        "promoted_spans": promoted,
    }
