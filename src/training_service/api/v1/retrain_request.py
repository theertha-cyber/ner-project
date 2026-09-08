"""Requesting a retrain from the decision surface.

A retrain is a training job. The only thing that distinguishes it from any other is what prompted
it, and that is metadata, not a different mechanism — so this endpoint does not have a mechanism.
It calls `training_jobs.create_training_job`, the same function the existing submission path
calls, and everything downstream is unchanged: the job lands in `pending_approval`, a System
Admin approves or rejects it, and approval is what enqueues the Celery task (design.md Decision
2, ADR-006).

**A separate module, on purpose.** This file exists so `training_jobs.py` does not have to
change. The approve and reject paths in that file are `training-approval`, which this change is
required to leave alone, and the surest way to leave code alone is not to open the file
(verification.md § Structural Evidence). Reuse here is a function call, not a copy.

**No hyperparameters, and nowhere to put them.** The request body carries no hyperparameter
fields — not ignored ones, absent ones — so there is no field for a caller to set and no code
here that could read one. ADR-009 puts hyperparameters at approval time, and a request that
accepted them would be the contradiction whether or not it acted on them (verification.md Risk
5).

**Tenant Admin only** (tasks.md 1.2). `create_training_job` already enforces it, and this
endpoint does not relax it: requester and approver stay different roles, which is what makes the
approval a gate rather than a formality.

**Zero accumulation does not block** (tasks.md 1.3). A retrain after a hyperparameter change is a
legitimate reason to train over unchanged data, and this surface reports evidence rather than
deciding on it. When nothing has accumulated the response says so and the job is created anyway;
the System Admin approving it can see the same figure.

Nothing here enqueues, schedules, or promotes anything.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.training_service.api.v1.schemas import TrainingJobCreate, TrainingJobResponse
from src.training_service.api.v1.training_jobs import (
    create_training_job,
    get_session,
    get_tenant_id,
)

router = APIRouter(prefix="/api/v1/training-retrain-requests", tags=["training-jobs"])


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


async def _unconsumed_review_span_count(session: AsyncSession, schema: str) -> int:
    """Production-review spans no completed run has consumed yet.

    A local count rather than a call into `annotation_service`'s accumulation report: this is
    used only to phrase a warning, and reaching across a service boundary to phrase a warning
    would make the request path depend on another service being up. The decision surface remains
    the authority on the figure itself — this endpoint states no number, only whether the count
    was zero.
    """
    result = await session.execute(
        text(
            f"SELECT COUNT(*) FROM {schema}.span_review_provenance p "
            f"LEFT JOIN {schema}.span_training_consumption c ON c.span_id = p.span_id "
            "WHERE c.span_id IS NULL AND p.served_by_base_model = false"
        )
    )
    return int(result.scalar() or 0)


@router.post("", status_code=201, response_model=TrainingJobResponse)
async def request_retrain(
    request: Request,
    response: Response,
    # The existing submission body, defaulted so a request needs no body at all. Bound
    # explicitly rather than omitted: with no body parameter FastAPI ignores whatever is sent,
    # so a caller supplying `learning_rate` would get a 201 and never learn it was dropped.
    # `TrainingJobCreate` forbids extra fields, which turns that into a 422 — the hyperparameter
    # is refused, in words, at the boundary (ADR-009).
    body: TrainingJobCreate = TrainingJobCreate(),
    session: AsyncSession = Depends(get_session),
) -> TrainingJobResponse:
    """Create an ordinary training job in `pending_approval`.

    Returns the created job, and sets `X-Retrain-Warning` when no new reviewed evidence has
    accumulated — a header rather than a refusal, because the response model is the ordinary
    training job and the warning is about the decision, not about the job.
    """
    tenant_id = get_tenant_id(request)

    # Read before creating, so the warning describes the state the requester was looking at
    # rather than one the job has already begun to change.
    accumulated = await _unconsumed_review_span_count(session, _schema(tenant_id))

    # The existing submission path, called rather than reimplemented. `body` is not a
    # placeholder for hyperparameters: `TrainingJobCreate` has no hyperparameter fields, and
    # `create_training_job` passes `None` to the repository regardless (ADR-009).
    job = await create_training_job(body, request, session)

    if accumulated == 0:
        # A header, not a 422. Blocking here would make this surface a gate over a decision it
        # exists only to inform, and would remove the one legitimate reason to retrain over
        # unchanged data: different hyperparameters (tasks.md 1.3).
        response.headers["X-Retrain-Warning"] = "no-accumulated-spans"

    return job
