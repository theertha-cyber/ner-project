"""Turning a reviewed prediction into a recorded outcome, and an outcome into a span.

One path, used by both review routes. The human endpoint and the LLM background job both call
`resolve_prediction`; neither has a shortcut past it. That is design.md Decision 4 expressed as
code rather than as a rule someone has to remember: span creation and accumulation accounting
never learn which route acted, so they cannot grow branches that diverge, and the LLM never gets
a privileged unaudited path into training data.

A span is defined by character offsets over the document text and its stored text is sliced from
that document at those offsets. Nothing in this module reads `corrected_value` — the existing
value-level correction flow records that "AcmeCorp" should read "Acme Corp", which is a
normalisation of what the text says, not a statement about where the entity is, and when it
differs in length from the source it corresponds to no span at all (design.md Decision 3).

A rejection records an outcome and produces nothing else. It writes no span and no explicit `O`
over the region: the reviewer rejected *this type at these offsets*, not every type over that
span, and asserting the stronger claim would reintroduce change 1's partial-labeling problem
(design.md Decision 12).

Nothing here creates, enqueues, or schedules a training job.
"""

import uuid

from sqlalchemy import text

from src.shared.confidence_routing import (
    OUTCOME_CORRECTED,
    OUTCOME_REJECTED,
    OUTCOMES,
    ROUTES,
    SPAN_PRODUCING_OUTCOMES,
)

# Where the reviewed prediction was drawn from. Both populations resolve through this module;
# only the population differs — the queue is the below-threshold one, the audit draw is over the
# auto-accepted one that would otherwise never be checked by anyone.
ORIGIN_QUEUE = "queue"
ORIGIN_AUDIT = "audit"

ORIGINS = (ORIGIN_QUEUE, ORIGIN_AUDIT)


class ReviewError(ValueError):
    """A malformed resolution. Raised rather than silently coerced: a review outcome becomes
    training data, so guessing what the reviewer meant is the wrong failure mode."""


def _slice_document_text(document_text: str, char_start: int, char_end: int) -> str:
    return (document_text or "")[char_start:char_end]


def compute_bio_tags(doc_text: str, char_start: int, char_end: int, entity_type: str) -> list[str]:
    """BIO tags over whitespace tokens intersecting the span.

    Mirrors `annotation_service.api.v1.spans._compute_bio_tags`, whose behaviour the training
    export depends on. Duplicated rather than imported to avoid a circular import between the
    spans endpoint module and this service; the two must stay in step, and a divergence is a
    defect the export tests are positioned to catch.
    """
    tags: list[str] = []
    char_offset = 0
    for token in (doc_text or "").split():
        token_start = char_offset
        token_end = char_offset + len(token)
        char_offset = token_end
        if char_offset < len(doc_text or "") and (doc_text or "")[char_offset] == " ":
            char_offset += 1
        if token_start >= char_end:
            break
        if token_end > char_start and token_start < char_end:
            tags.append(f"B-{entity_type}" if not tags else f"I-{entity_type}")
    return tags


def normalize_resolution(prediction: dict, body: dict) -> dict:
    """Validate a submitted resolution and settle the final type and offsets.

    A `confirmed` outcome takes the prediction's own type and offsets — confirming means "as-is",
    so accepting overrides alongside it would make the word meaningless. A `corrected` outcome
    takes whichever of type, start and end the reviewer supplied and the prediction's value for
    the rest, and must differ from the prediction in at least one of them or it is a confirmation
    wearing the wrong label. A `rejected` outcome carries the prediction's type and offsets so
    the row still records what was rejected; no span comes of it either way.
    """
    outcome = body.get("outcome")
    if outcome not in OUTCOMES:
        raise ReviewError(f"outcome must be one of {list(OUTCOMES)}")

    route = body.get("route")
    if route not in ROUTES:
        raise ReviewError(f"route must be one of {list(ROUTES)}")

    entity_type = prediction["entity_type"]
    char_start = prediction["char_start"]
    char_end = prediction["char_end"]

    if outcome == OUTCOME_CORRECTED:
        entity_type = body.get("entity_type", entity_type)
        char_start = body.get("char_start", char_start)
        char_end = body.get("char_end", char_end)
        if not isinstance(char_start, int) or not isinstance(char_end, int):
            raise ReviewError("char_start and char_end must be integers")
        if char_end <= char_start:
            raise ReviewError("char_end must be greater than char_start")
        unchanged = (
            entity_type == prediction["entity_type"]
            and char_start == prediction["char_start"]
            and char_end == prediction["char_end"]
        )
        if unchanged:
            raise ReviewError(
                "a corrected outcome must change the entity type or the offsets; "
                "use outcome 'confirmed' to accept the prediction as-is"
            )

    return {
        "outcome": outcome,
        "route": route,
        "entity_type": entity_type,
        "char_start": char_start,
        "char_end": char_end,
    }


async def record_outcome(
    conn,
    schema: str,
    prediction: dict,
    resolution: dict,
    reviewer: str | None,
    origin: str = ORIGIN_QUEUE,
) -> str:
    """Insert the review outcome and return its id.

    The row carries its own copy of the document, the model version, the reviewer's type and
    offsets, and the model's — everything accumulation accounting and route-agreement comparison
    need — because the prediction row it came from is deleted next.
    """
    if origin not in ORIGINS:
        raise ReviewError(f"origin must be one of {list(ORIGINS)}")

    outcome_id = str(uuid.uuid4())
    await conn.execute(
        text(
            f"INSERT INTO {schema}.review_outcomes "
            "(id, prediction_id, document_id, outcome, route, entity_type, char_start, "
            " char_end, predicted_entity_type, predicted_char_start, predicted_char_end, "
            " predicted_confidence, model_version, served_by_base_model, origin, reviewer) "
            "VALUES (:id, :prediction_id, :document_id, :outcome, :route, :entity_type, "
            "        :char_start, :char_end, :predicted_entity_type, :predicted_char_start, "
            "        :predicted_char_end, :predicted_confidence, :model_version, :base_model, "
            "        :origin, :reviewer)"
        ),
        {
            "id": outcome_id,
            "prediction_id": prediction["id"],
            "document_id": prediction["document_id"],
            "outcome": resolution["outcome"],
            "route": resolution["route"],
            "entity_type": resolution["entity_type"],
            "char_start": resolution["char_start"],
            "char_end": resolution["char_end"],
            "predicted_entity_type": prediction["entity_type"],
            "predicted_char_start": prediction["char_start"],
            "predicted_char_end": prediction["char_end"],
            "predicted_confidence": prediction.get("confidence"),
            "model_version": prediction["model_version"],
            "base_model": prediction["served_by_base_model"],
            "origin": origin,
            "reviewer": reviewer,
        },
    )
    return outcome_id


async def create_span_from_outcome(
    conn,
    schema: str,
    prediction: dict,
    resolution: dict,
    outcome_id: str,
    document_text: str,
) -> str | None:
    """Create the confirmed span a confirmed or corrected outcome implies, or `None`.

    The span's `text_content` is sliced from the document at the resolved offsets. It is never
    taken from the caller and never from a corrected value — a span whose stored text is not what
    the document says at those offsets is not training data, it is a fiction the model would be
    asked to reproduce.

    `span_review_provenance` is written in the same statement sequence, so a production-review
    span cannot exist without the row that says where it came from. Together with `039`'s
    `span_batch_provenance` this is what makes the three origins distinguishable: a row here
    means production review, a row there means batch acceptance, neither means individual manual
    annotation.
    """
    if resolution["outcome"] not in SPAN_PRODUCING_OUTCOMES:
        return None

    span_id = str(uuid.uuid4())
    char_start = resolution["char_start"]
    char_end = resolution["char_end"]
    entity_type = resolution["entity_type"]
    text_content = _slice_document_text(document_text, char_start, char_end)

    await conn.execute(
        text(
            f"INSERT INTO {schema}.spans "
            "(id, document_id, entity_type, char_start, char_end, text_content, confidence, "
            " bio_tags) "
            "VALUES (:id, :document_id, :entity_type, :char_start, :char_end, :text_content, "
            "        1.0, :bio_tags)"
        ),
        {
            "id": span_id,
            "document_id": prediction["document_id"],
            "entity_type": entity_type,
            "char_start": char_start,
            "char_end": char_end,
            "text_content": text_content,
            # 1.0, not the model's confidence: a human or the LLM has now judged this span, so
            # what the row records is the reviewer's certainty, not the prediction's. The
            # model's figure survives on the outcome as `predicted_confidence`.
            "bio_tags": compute_bio_tags(document_text, char_start, char_end, entity_type),
        },
    )
    await conn.execute(
        text(
            f"INSERT INTO {schema}.span_review_provenance "
            "(span_id, outcome_id, model_version, served_by_base_model) "
            "VALUES (:span_id, :outcome_id, :model_version, :base_model)"
        ),
        {
            "span_id": span_id,
            "outcome_id": outcome_id,
            "model_version": prediction["model_version"],
            "base_model": prediction["served_by_base_model"],
        },
    )
    return span_id


async def discard_prediction(conn, schema: str, prediction_id: str) -> None:
    """Delete the routed prediction now that its information lives in an outcome.

    The resolution half of Decision 11's retention bound. Safe precisely because
    `review_outcomes` copied everything: this deletes a row whose content has already been
    preserved in the form that matters.
    """
    await conn.execute(
        text(f"DELETE FROM {schema}.routed_predictions WHERE id = :id"),
        {"id": prediction_id},
    )


async def resolve_prediction(
    conn,
    schema: str,
    prediction: dict,
    body: dict,
    reviewer: str | None,
    document_text: str,
    origin: str = ORIGIN_QUEUE,
) -> dict:
    """The whole resolution, as one unit: validate, record the outcome, create any span, and
    discard the prediction.

    Both review routes call exactly this. An LLM review job that wanted to write a span directly
    would have to bypass the only function that writes one, which is what makes Decision 4
    checkable rather than merely stated.

    Two of those four steps are conditional on `origin`, because an audit is a measuring
    instrument rather than a second review queue (design.md Decision 16):

    * **No span** from an audit outcome. Accumulation is meant to record new evidence about what
      the model gets wrong; filling it from high-confidence predictions a reviewer agreed with
      would bias the training set toward what the model already handles, and would make the
      figure grow with audit frequency.
    * **No discard** of an audited prediction. It keeps its `accepted` disposition, so successive
      audits sample from a population that has not been consumed by the previous one — which is
      what makes the `population_size` recorded on each audit comparable at all.

    Both are parameters of the shared path rather than a separate audit implementation, so the
    single-span-writer property survives them.
    """
    resolution = normalize_resolution(prediction, body)
    outcome_id = await record_outcome(conn, schema, prediction, resolution, reviewer, origin)

    span_id = None
    if origin == ORIGIN_QUEUE:
        span_id = await create_span_from_outcome(
            conn, schema, prediction, resolution, outcome_id, document_text
        )
        await discard_prediction(conn, schema, prediction["id"])

    return {
        "outcome_id": outcome_id,
        "outcome": resolution["outcome"],
        "route": resolution["route"],
        "origin": origin,
        "entity_type": resolution["entity_type"],
        "char_start": resolution["char_start"],
        "char_end": resolution["char_end"],
        "span_id": span_id,
        "rejected": resolution["outcome"] == OUTCOME_REJECTED,
    }
