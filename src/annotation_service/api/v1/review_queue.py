"""The low-confidence review queue and its human resolution route.

Two surfaces over the predictions `extraction_service` routed:

  * `GET /review-queue` lists what is waiting, with enough document context for a reviewer to
    judge a span without opening the document separately.
  * `POST /review-queue/{id}/resolve` records one reviewer's decision.

The resolution endpoint is a thin shell over `review_resolution.resolve_prediction`, and
deliberately so. That function is the only path in this change that writes a span, and the LLM
review job calls exactly the same one (design.md Decision 4). Putting the span-writing logic here
instead would give the human route a copy the LLM route could drift away from, which is the
branching Decision 4 exists to prevent.

`route` is not read from the request body. A caller reaching this endpoint is a human reviewer by
construction, so the route is stamped here rather than accepted as input — a body-supplied route
would let the human surface record LLM-route outcomes and make the route-agreement comparison
Decision 10 is waiting on meaningless.

Everything resolves the tenant schema the way every other `annotation_service` endpoint does, and
every statement is scoped to it (ADR-001).

Nothing here creates, enqueues, or schedules a training job.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.annotation_service.api.v1.spans import get_session, get_tenant_id
from src.annotation_service.services.accumulation import (
    accumulation_report,
    current_model_version,
)
from src.annotation_service.services.audit_sampling import (
    AUDIT_STATUS_COMPLETED,
    auditable_population,
    close_audit,
    disposition_for,
    open_audit,
)
from src.annotation_service.services.review_resolution import (
    ORIGIN_AUDIT,
    ORIGIN_QUEUE,
    ReviewError,
    resolve_prediction,
)
from src.shared.config import settings
from src.shared.confidence_routing import DISPOSITION_QUEUED, ROUTE_HUMAN

router = APIRouter(tags=["review-queue"])

# How much document text to send either side of the span. Enough for a reviewer to see the
# sentence a prediction sits in, which is what "is this an organisation?" actually depends on,
# without shipping a whole document per queue row.
CONTEXT_CHARS = 200


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _user_id(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


async def _document_text(session: AsyncSession, schema: str, document_id: str) -> str:
    """The document's text, or empty string when it has none.

    Read from `document_text_spans` exactly as the spans endpoint reads it, so a span created
    through review and one created through manual annotation are slicing the same string.
    """
    result = await session.execute(
        text(f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id LIMIT 1"),
        {"doc_id": document_id},
    )
    row = result.fetchone()
    return (row[0] or "") if row else ""


@router.get("/api/v1/review-queue")
async def list_review_queue(
    request: Request = None,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Predictions awaiting review, oldest first.

    Oldest first because the queue is work to be done, not a feed: a prediction that has been
    waiting longest is the one whose document context is most likely to have gone stale, and
    newest-first would let a busy tenant's backlog never be reached at all.

    Only `queued` rows are listed. Auto-accepted predictions live in the same table but are not
    review work — they are reached, if at all, through an audit draw (design.md Decision 6).
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    # Deletion here is a status flag, not a row removal (`delete_document` never drops the
    # `documents` row), so an un-filtered join still matches a prediction whose document is
    # gone. Left in, that prediction is unreviewable — its text spans were cleared with the
    # document, so every offset reads as empty — and unreviewable work should never enter a
    # review queue in the first place.
    total_result = await session.execute(
        text(
            f"SELECT COUNT(*) FROM {schema}.routed_predictions p "
            f"JOIN {schema}.documents d ON d.id = p.document_id "
            "WHERE p.disposition = :disposition AND d.status != 'deleted'"
        ),
        {"disposition": DISPOSITION_QUEUED},
    )
    total = total_result.scalar() or 0

    result = await session.execute(
        text(
            f"SELECT p.id, p.document_id, d.filename, p.entity_type, p.value, p.confidence, "
            f"       p.char_start, p.char_end, p.model_version, p.served_by_base_model, "
            f"       p.below_business_threshold, p.created_at "
            f"FROM {schema}.routed_predictions p "
            f"JOIN {schema}.documents d ON d.id = p.document_id "
            "WHERE p.disposition = :disposition AND d.status != 'deleted' "
            "ORDER BY p.created_at ASC, p.id ASC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"disposition": DISPOSITION_QUEUED, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    # One text read per distinct document rather than per row: a queue page is frequently many
    # predictions over a handful of documents, and re-reading the same document text for each
    # would be the dominant cost of listing.
    texts: dict[str, str] = {}
    for row in rows:
        if row[1] not in texts:
            texts[row[1]] = await _document_text(session, schema, row[1])

    items = []
    for row in rows:
        doc_text = texts.get(row[1], "")
        char_start, char_end = row[6], row[7]
        context_start = max(0, char_start - CONTEXT_CHARS)
        context_end = min(len(doc_text), char_end + CONTEXT_CHARS)
        items.append(
            {
                "id": row[0],
                "document_id": row[1],
                "filename": row[2],
                "entity_type": row[3],
                "value": row[4],
                "confidence": row[5],
                "char_start": char_start,
                "char_end": char_end,
                "model_version": row[8],
                "served_by_base_model": row[9],
                "below_business_threshold": row[10],
                "created_at": row[11].isoformat() if row[11] else None,
                # The document text around the span, plus where the span sits inside that
                # excerpt, so a reviewer can highlight it without recomputing offsets against a
                # window the server chose.
                "context": doc_text[context_start:context_end],
                "context_char_start": context_start,
                # What the document actually says at those offsets. Sent alongside the stored
                # `value` because a disagreement between the two is itself worth seeing — it
                # means the document changed under the prediction.
                "text_at_offsets": doc_text[char_start:char_end],
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/api/v1/review-queue/{prediction_id}/resolve")
async def resolve_queued_prediction(
    prediction_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Record a human reviewer's decision on one queued prediction.

    Accepts `outcome` of `confirmed`, `corrected` or `rejected`, plus `entity_type`,
    `char_start` and `char_end` when correcting. A `confirmed` outcome takes the prediction's own
    type and offsets; supplying overrides alongside it is ignored rather than honoured, because
    "confirmed" means as-is and a confirmation that silently moved the span would be a correction
    recorded under the wrong name.

    Resolving an already-resolved prediction is a 404, not a conflict: the row is deleted the
    moment its outcome is recorded (design.md Decision 11), so from here a resolved prediction
    and one that never existed are the same thing.
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT id, document_id, entity_type, value, confidence, char_start, char_end, "
            f"       model_version, served_by_base_model, disposition "
            f"FROM {schema}.routed_predictions WHERE id = :id"
        ),
        {"id": prediction_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Queued prediction not found"},
        )
    if row[9] != DISPOSITION_QUEUED:
        # An auto-accepted prediction is not queue work. It is reachable only through an audit
        # draw, which resolves it with `origin='audit'` so the two populations stay
        # distinguishable in the outcome record.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NOT_QUEUED",
                "message": "This prediction was auto-accepted and is not review-queue work",
            },
        )

    prediction = {
        "id": row[0],
        "document_id": row[1],
        "entity_type": row[2],
        "value": row[3],
        "confidence": row[4],
        "char_start": row[5],
        "char_end": row[6],
        "model_version": row[7],
        "served_by_base_model": row[8],
    }

    document_text = await _document_text(session, schema, prediction["document_id"])

    try:
        outcome = await resolve_prediction(
            session,
            schema,
            prediction,
            # The route is stamped, not accepted from the caller: this endpoint *is* the human
            # route, and letting a body claim otherwise would corrupt the route-agreement
            # comparison Decision 10 depends on.
            {**body, "route": ROUTE_HUMAN},
            _user_id(request),
            document_text,
            origin=ORIGIN_QUEUE,
        )
    except ReviewError as e:
        raise HTTPException(
            status_code=422, detail={"code": "VALIDATION_ERROR", "message": str(e)}
        )

    await session.commit()
    return outcome


@router.get("/api/v1/review-accumulation")
async def get_review_accumulation(
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """How many production-review spans have accumulated against the serving model version.

    Reports and stops. There is no code path from this endpoint into training submission, and
    none should be added: the decision to retrain belongs to a person, and change 6 owns it
    (design.md Non-Goals, verification.md Risk 5).

    Deliberately a separate endpoint from `training-readiness`, and deliberately carrying a
    `note` that says what it is not. Accumulation is a delta since a specific version was
    trained; readiness is a per-entity-type count against ADR-010's threshold. They are
    different quantities answering different questions, and presenting them as one number would
    make both meaningless.
    """
    tenant_id = get_tenant_id(request)
    return await accumulation_report(session, _schema(tenant_id))


# --------------------------------------------------------------------------------------------
# Audit sampling of the auto-accept path.
#
# The accept path is otherwise the only path in this change with no feedback: nobody looks at a
# high-confidence prediction, so a model that is confidently wrong about one entity type produces
# no signal and quietly degrades the extracted data (design.md Decision 6).
#
# An audit measures and stops. It does not consume the population it samples from, and it does
# not create training data (design.md Decision 16).


@router.post("/api/v1/audits", status_code=201)
async def open_audit_sample(
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Draw an audit sample over the tenant's un-audited auto-accepted predictions.

    Size is `min(cap, max(floor, ceil(fraction * N)))` from configuration (design.md Decision
    13). A population smaller than the floor is audited whole — that is the floor doing its job
    on a small tenant, not a special case.

    Returns 204 with no body when there is nothing to audit. No audit row is written for an empty
    population: a recorded audit with a null rate is a measurement that never happened, and it
    would sit in the history as noise a reader has to learn to skip.
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    model_version = await current_model_version(session, schema)
    population = await auditable_population(session, schema, model_version)

    audit = await open_audit(
        session,
        schema,
        population,
        model_version,
        settings.audit_sample_floor,
        settings.audit_sample_fraction,
        settings.audit_sample_cap,
    )
    if audit is None:
        return Response(status_code=204)

    await session.commit()

    texts = {}
    for prediction in audit["predictions"]:
        if prediction["document_id"] not in texts:
            texts[prediction["document_id"]] = await _document_text(
                session, schema, prediction["document_id"]
            )

    return {
        "audit_id": audit["audit_id"],
        "model_version": audit["model_version"],
        "population_size": audit["population_size"],
        "sample_size": audit["sample_size"],
        "predictions": [
            {
                **prediction,
                "text_at_offsets": texts.get(prediction["document_id"], "")[
                    prediction["char_start"] : prediction["char_end"]
                ],
            }
            for prediction in audit["predictions"]
        ],
    }


@router.post("/api/v1/audits/{audit_id}/complete")
async def complete_audit_sample(
    audit_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Submit the reviewer's judgements for a drawn sample and record the agreement rate.

    Each judgement goes through `resolve_prediction` with `origin='audit'` — the same path a
    queue review takes, which is what makes the two rates comparable. What differs is what that
    path then does: no span is created, and the prediction keeps its accepted disposition
    (design.md Decision 16).

    Only predictions actually drawn into this audit are accepted. A judgement naming some other
    prediction is a 422 rather than a silently ignored entry: a rate computed over a sample that
    is not the recorded one is exactly the unfalsifiable measurement that storing the drawn
    identities was meant to prevent.
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT sampled_prediction_ids, status FROM {schema}.audit_samples WHERE id = :id"
        ),
        {"id": audit_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Audit not found"}
        )
    if row[1] == AUDIT_STATUS_COMPLETED:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_COMPLETED", "message": "This audit is already recorded"},
        )

    sampled_ids = row[0] if isinstance(row[0], list) else json.loads(row[0])
    judgements = body.get("judgements") or []
    if not judgements:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "judgements is required"},
        )

    unknown = {j.get("prediction_id") for j in judgements} - set(sampled_ids)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"judgements name predictions outside this audit: {sorted(unknown)}",
            },
        )

    dispositions = []
    for judgement in judgements:
        prediction_id = judgement["prediction_id"]
        prediction_result = await session.execute(
            text(
                f"SELECT id, document_id, entity_type, value, confidence, char_start, char_end, "
                f"       model_version, served_by_base_model "
                f"FROM {schema}.routed_predictions WHERE id = :id"
            ),
            {"id": prediction_id},
        )
        prediction_row = prediction_result.fetchone()
        if prediction_row is None:
            # Drawn, then removed by the retention bound before it could be judged. Skipped
            # rather than counted: an unjudged prediction is not evidence either way.
            continue

        prediction = {
            "id": prediction_row[0],
            "document_id": prediction_row[1],
            "entity_type": prediction_row[2],
            "value": prediction_row[3],
            "confidence": prediction_row[4],
            "char_start": prediction_row[5],
            "char_end": prediction_row[6],
            "model_version": prediction_row[7],
            "served_by_base_model": prediction_row[8],
        }
        document_text = await _document_text(session, schema, prediction["document_id"])

        try:
            await resolve_prediction(
                session,
                schema,
                prediction,
                {**judgement, "route": ROUTE_HUMAN},
                _user_id(request),
                document_text,
                origin=ORIGIN_AUDIT,
            )
        except ReviewError as e:
            raise HTTPException(
                status_code=422, detail={"code": "VALIDATION_ERROR", "message": str(e)}
            )

        dispositions.append(
            {
                "prediction_id": prediction_id,
                "disposition": disposition_for(prediction, judgement),
            }
        )

    outcome = await close_audit(session, schema, audit_id, dispositions, _user_id(request))
    await session.commit()
    return outcome
