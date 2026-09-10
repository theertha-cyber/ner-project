"""The retraining decision surface.

Change 5 produced an accumulation figure and left it unconnected to the action it informs. This
endpoint is where that figure meets the decision: how much reviewed evidence has built up since
the serving model was trained, broken down by entity type, with the serving version named and
whether a run is currently executing.

It reports and stops. There is no path from here into training submission — requesting a retrain
is a separate, explicit POST to `training_service`, which lands in `pending_approval` like any
other job. Nothing here compares the figure against a constant, and no constant exists here to
compare it against: a threshold with a job behind it is the auto-trigger this plan deliberately
reversed, and a threshold with nothing behind it is a number pretending to be advice
(design.md Decision 3, verification.md Risk 1).

**Why the in-flight indicator.** Consumed spans are recorded at completion, so a figure read
while a run executes still counts spans that run is about to consume. That is the correct
behaviour — recording at submission would zero the figure for a job that might be rejected — but
it makes the number stale in a way a reader cannot see. `training_run_in_flight` says so. It is a
fact about the state, not a recommendation.

**Why it is not readiness.** ADR-010 owns dataset readiness: per entity type, at its own
threshold, answering "is there enough data to train at all?". Accumulation answers "has anything
new arrived since the last time we did?". The per-type breakdown here makes them look alike, so
the response says in words that they are not, and this module imports no readiness threshold —
`gateway/api/v1/training_readiness.py` remains the only place that one lives (task 3.3).

Tenant scoping is by schema, as everywhere else in this service (ADR-001).
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.annotation_service.api.v1.spans import get_session, get_tenant_id
from src.annotation_service.services.accumulation import accumulation_report, eligible_overview

router = APIRouter(tags=["retraining-decision"])

# Job states that mean a run is under way or about to be. `pending_approval` counts: the spans
# are not consumed yet, but a decision has already been asked for, and a second request would
# queue a second job over substantially the same dataset.
IN_FLIGHT_JOB_STATUSES = ("pending_approval", "queued", "running")


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


async def training_run_in_flight(session: AsyncSession, schema: str) -> bool:
    """Whether a training job for this tenant is awaiting approval, queued, or running."""
    result = await session.execute(
        text(
            f"SELECT 1 FROM {schema}.training_jobs "
            "WHERE status = ANY(:statuses) LIMIT 1"
        ),
        {"statuses": list(IN_FLIGHT_JOB_STATUSES)},
    )
    return result.fetchone() is not None


@router.get("/api/v1/retraining-decision")
async def get_retraining_decision(
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Evidence for the retrain decision. No verdict, no threshold, no job.

    `has_trained_model` is false for a tenant served by ADR-008's base model, and the
    accumulation fields are then absent rather than zero. "Nothing new since version 3" and
    "there is no version 3" are opposite situations that a bare zero makes identical, and the
    one that reads as "nothing to do" is the one where a first training run is exactly what is
    needed (design.md Decision 5).
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    report = await accumulation_report(session, schema)
    overview = await eligible_overview(session, schema)
    in_flight = await training_run_in_flight(session, schema)
    has_trained_model = report["model_version"] is not None

    response = {
        "has_trained_model": has_trained_model,
        "serving_model_version": report["model_version"],
        "training_run_in_flight": in_flight,
        # Carried through rather than recomputed. Change 5 owns what the figure counts and what
        # it excludes; a second implementation here would be a second answer to the same
        # question (design.md Decision 1 on why one place, not two).
        "spans_from_base_model": report["spans_from_base_model"],
        "kind": report["kind"],
        "note": report["note"],
        # Report only: counts of training-eligible units not yet consumed by a completed
        # run, per source. Never compared against a threshold, never a gate.
        "eligible_overview": overview,
    }

    if has_trained_model:
        response["spans_accumulated"] = report["spans_accumulated"]
        response["by_entity_type"] = report["by_entity_type"]
        response["by_source"] = report["by_source"]
    else:
        # Said in words as well as in the flag, because the flag alone is easy to render as a
        # zero by a caller that was not expecting this branch.
        response["state"] = "no_trained_model"
        response["state_detail"] = (
            "This tenant has no trained model and is served by the base model. There is no "
            "trained version for accumulation to be measured against."
        )

    if in_flight:
        response["in_flight_detail"] = (
            "A training job is pending approval, queued, or running. Spans are recorded as "
            "consumed only when a run completes, so this figure still includes spans that run "
            "may consume."
        )

    return response
