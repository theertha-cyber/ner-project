"""Sizing the audit draw over the auto-accepted population.

The accept path is otherwise the only path in this change with no feedback whatsoever: nobody
looks at a high-confidence prediction, so a model that is confidently wrong about one entity type
produces no signal at all and just quietly degrades the extracted data (design.md Decision 6).

Only the *size* of the draw lives here. The draw itself and the agreement measurement are
change 4's `batch_acceptance.draw_sample` and `batch_acceptance.agreement_rate`, re-exported
below and used unchanged — a second implementation of "pick n at random" and "what fraction did
the reviewer agree with" would be two things that can disagree about the same question, and the
existing pair is already tested.
"""

import math

from src.annotation_service.services.batch_acceptance import (  # noqa: F401  (re-exported)
    DISPOSITION_AGREE,
    DISPOSITIONS,
    agreement_rate,
    draw_sample,
)


def audit_sample_size(population: int, floor: int, fraction: float, cap: int) -> int:
    """`min(cap, max(floor, ceil(fraction * N)))`, and never more than the population itself.

    Design.md Decision 13. The floor keeps the rate meaningful on a small tenant, where the
    fraction alone would sample almost nothing; the cap stops a large tenant drawing a sample
    nobody can review. When the population is below the floor the whole population is audited —
    that is the floor doing its job, not a special case.
    """
    if population <= 0:
        return 0
    proportional = math.ceil(fraction * population)
    size = min(cap, max(floor, proportional))
    return min(size, population)


# --------------------------------------------------------------------------------------------
# Drawing an audit and recording its result.
#
# The draw and the rate come from change 4 (`draw_sample`, `agreement_rate`, re-exported above)
# and are used unchanged. What is here is the part that is specific to auditing the accept path:
# which population to draw from, and what to record about the draw.
#
# Nothing here creates, enqueues, or schedules a training job.

import json
import uuid

from sqlalchemy import text

from src.annotation_service.services.review_resolution import ORIGIN_AUDIT

AUDIT_STATUS_IN_REVIEW = "in_review"
AUDIT_STATUS_COMPLETED = "completed"


async def auditable_population(session, schema: str, model_version: str) -> list[dict]:
    """Auto-accepted predictions from `model_version` that have not already been audited.

    Scoped to one model version because that is what the audit is *about*. The spec asks for the
    rate to be recorded against "the model version audited", and a population spanning versions
    would produce a single rate describing several models at once — which would be a number
    nobody could act on. Predictions from a superseded version are not re-audited: what they say
    about a model that is no longer serving cannot change what to do next.

    "Not already audited" is a join against `review_outcomes` on `origin = 'audit'` rather than a
    column on the prediction. An audit does not consume what it measures (design.md Decision 16),
    so the audited rows are still `accepted` and still in this table; what marks them is the
    outcome that exists for them. Deriving it from the outcome keeps one fact in one place.
    """
    result = await session.execute(
        text(
            f"SELECT p.id, p.document_id, p.entity_type, p.value, p.confidence, p.char_start, "
            f"       p.char_end, p.model_version, p.served_by_base_model "
            f"FROM {schema}.routed_predictions p "
            f"WHERE p.disposition = 'accepted' "
            "  AND p.model_version = :model_version "
            f"  AND NOT EXISTS ("
            f"    SELECT 1 FROM {schema}.review_outcomes o "
            f"    WHERE o.prediction_id = p.id AND o.origin = :audit_origin) "
            "ORDER BY p.created_at ASC, p.id ASC"
        ),
        {"audit_origin": ORIGIN_AUDIT, "model_version": str(model_version)},
    )
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
        }
        for row in result.fetchall()
    ]


async def open_audit(session, schema: str, population: list[dict], model_version: str,
                     floor: int, fraction: float, cap: int, rng=None) -> dict | None:
    """Draw a sample and record it, returning the audit and the predictions drawn.

    Returns `None` for an empty population: an audit that measured nothing has nothing to say,
    and recording a row for it would put a `null` rate in the history that a reader has to learn
    to ignore.

    The drawn identities are written at selection time and never recomputed. A re-drawn sample
    would make the recorded agreement rate unfalsifiable, which is the same reason change 4's
    `batch_acceptance_records` stores its own.
    """
    if not population:
        return None

    size = audit_sample_size(len(population), floor, fraction, cap)
    if size <= 0:
        return None

    by_id = {item["id"]: item for item in population}
    sampled_ids = draw_sample(list(by_id), size, sampling_enabled=True, rng=rng)

    audit_id = str(uuid.uuid4())
    await session.execute(
        text(
            f"INSERT INTO {schema}.audit_samples "
            "(id, model_version, population_size, sample_size, sampled_prediction_ids, status) "
            "VALUES (:id, :mv, :population, :size, CAST(:ids AS JSONB), :status)"
        ),
        {
            "id": audit_id,
            "mv": model_version,
            "population": len(population),
            "size": len(sampled_ids),
            "ids": json.dumps(sampled_ids),
            "status": AUDIT_STATUS_IN_REVIEW,
        },
    )
    return {
        "audit_id": audit_id,
        "model_version": model_version,
        "population_size": len(population),
        "sample_size": len(sampled_ids),
        "predictions": [by_id[pid] for pid in sampled_ids],
    }


def disposition_for(prediction: dict, outcome_body: dict) -> str:
    """What the reviewer's answer says about the model, in change 4's vocabulary.

    Reused rather than redefined so an agreement rate measured here and one measured on a
    pre-label batch mean the same thing. `agree` is an exact match — same type, same offsets —
    which is the definition change 4 adopted and the one `agreement_rate` counts.
    """
    outcome = outcome_body.get("outcome")
    if outcome == "confirmed":
        return DISPOSITION_AGREE
    if outcome == "rejected":
        return "reject"
    if outcome_body.get("entity_type", prediction["entity_type"]) != prediction["entity_type"]:
        return "retype"
    return "boundary"


async def close_audit(session, schema: str, audit_id: str, dispositions: list[dict],
                      reviewer: str | None = None) -> dict:
    """Record the measured rate against the sample size and the audited model version.

    All three together, because a rate alone is not evidence: 100% over a sample of 2 and 100%
    over a sample of 100 are different claims, and neither means anything without knowing which
    model produced the predictions.
    """
    agreed, reviewed, rate = agreement_rate(dispositions)
    await session.execute(
        text(
            f"UPDATE {schema}.audit_samples SET "
            " agreement_rate = :rate, reviewed_count = :reviewed, agreed_count = :agreed, "
            " dispositions = CAST(:dispositions AS JSONB), status = :status, "
            " reviewer = :reviewer, completed_at = NOW() "
            "WHERE id = :id"
        ),
        {
            "rate": rate,
            "reviewed": reviewed,
            "agreed": agreed,
            "dispositions": json.dumps(dispositions),
            "status": AUDIT_STATUS_COMPLETED,
            "reviewer": reviewer,
            "id": audit_id,
        },
    )
    return {"audit_id": audit_id, "agreement_rate": rate, "reviewed": reviewed, "agreed": agreed}
