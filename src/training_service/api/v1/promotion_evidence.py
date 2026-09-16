"""Evidence for the promotion decision.

Promotion was already a human action before this change — `models.promote_model` archives the
previous version and warms serving, and nothing calls it but a Tenant Admin. What it lacked was
anything to decide on: the only evidence a run finished was that a run finished. This endpoint
supplies the metrics.

It is read-only and it lives in its own module so `models.py` is untouched. The promote and
demote paths are `model-registry`, which this change is required to leave exactly as it is
(verification.md § Structural Evidence); a GET added to that file would have to be re-read line
by line to prove that, and one added here does not.

**No verdict.** Not "version 4 is better", not a ranking, not a recommendation — there is no
field in this response that could carry one. Computing one would be the system making the
decision this surface exists to inform, and it would require a comparability judgement the data
does not support (design.md Decision 4, verification.md Risk 7).

**Which is exactly why the dataset sizes are here.** Change 3 established that metrics from runs
over materially different data are not comparable. Two numbers side by side invite a comparison
regardless, so the response carries the span count each version trained on and says, when they
differ materially, that the comparison is not a straight one. A surface that silently invited an
invalid comparison would be worse than one showing nothing: it would produce confident wrong
promotions rather than uncertain ones.

Tenant scoping is by schema (ADR-001).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.training_service.api.v1.training_jobs import get_session, get_tenant_id

router = APIRouter(prefix="/api/v1/training-promotion-evidence", tags=["model-registry"])

# Relative difference in trained-on span count at or above which two runs are reported as not
# directly comparable (tasks.md 1.4).
#
# A presentation constant, and only that. It gates a sentence, never a job and never a
# promotion: nothing reads it to decide anything, and there is no path from it to an action. It
# is emphatically not a dataset threshold — ADR-010 owns the only one of those, it is per entity
# type, it is about whether there is enough data to train at all, and this has nothing to do with
# it.
#
# 25% because it is the smallest difference at which "the datasets are comparable" stops being a
# defensible thing to leave unsaid, and because the alternative — always printing the caveat —
# teaches a reader to skip it, which costs the caveat its meaning on the runs that need it.
MATERIAL_DATASET_DIFFERENCE = 0.25


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


async def _version_row(session: AsyncSession, schema: str, version_number: int) -> dict | None:
    result = await session.execute(
        text(
            f"SELECT COALESCE(version_number, version) AS version_number, status, metrics, "
            f"       training_job_id, created_at, promoted_at "
            f"FROM {schema}.model_versions "
            "WHERE COALESCE(version_number, version) = :v LIMIT 1"
        ),
        {"v": version_number},
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def _promoted_row(session: AsyncSession, schema: str) -> dict | None:
    result = await session.execute(
        text(
            f"SELECT COALESCE(version_number, version) AS version_number, status, metrics, "
            f"       training_job_id, created_at, promoted_at "
            f"FROM {schema}.model_versions "
            "WHERE status = 'promoted' "
            "ORDER BY COALESCE(version_number, version) DESC LIMIT 1"
        )
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def _trained_on_span_count(session: AsyncSession, schema: str, version_number) -> int:
    """Confirmed spans recorded as consumed by the run that produced this version.

    Read from `span_training_consumption`, which the training worker writes at completion. A
    version trained before that writer existed has no rows and reports 0 — correct as an answer
    to "what did we record?", and the reason the comparability check below treats a zero as
    unknown rather than as a real count.
    """
    result = await session.execute(
        text(
            f"SELECT COUNT(*) FROM {schema}.span_training_consumption "
            "WHERE model_version = :v"
        ),
        {"v": str(version_number)},
    )
    return int(result.scalar() or 0)


def dataset_sizes_comparable(candidate_count: int, current_count: int) -> bool | None:
    """Whether two trained-on counts are close enough to read the metrics side by side.

    `None` — not `True` — when either count is zero. An unrecorded dataset size is not a small
    one, and returning `True` there would assert comparability from an absence of evidence,
    which is the specific mistake this whole surface is arranged to avoid.
    """
    if candidate_count <= 0 or current_count <= 0:
        return None
    larger = max(candidate_count, current_count)
    smaller = min(candidate_count, current_count)
    return (larger - smaller) / larger < MATERIAL_DATASET_DIFFERENCE


@router.get("/{version_number}")
async def get_promotion_evidence(
    version_number: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str | None = Query(
        None, description="Tenant ID (system admin only — overrides JWT tenant)"
    ),
):
    """The candidate's metrics beside the promoted version's, with what each was trained on."""
    role = getattr(request.state, "role", None)
    if role == "system_admin":
        if not tenant_id:
            raise HTTPException(
                status_code=400, detail="System admin must provide tenant_id query parameter"
            )
    else:
        tenant_id = get_tenant_id(request)

    schema = _schema(tenant_id)

    candidate = await _version_row(session, schema, version_number)
    if not candidate:
        raise HTTPException(status_code=404, detail="Model version not found")

    candidate_spans = await _trained_on_span_count(
        session, schema, candidate["version_number"]
    )
    candidate_block = {
        "version_number": int(candidate["version_number"]),
        "status": candidate["status"],
        "metrics": candidate.get("metrics") or {},
        "trained_on_span_count": candidate_spans,
        "training_job_id": candidate.get("training_job_id"),
        "created_at": candidate.get("created_at"),
    }

    promoted = await _promoted_row(session, schema)
    # A candidate that is itself the promoted version has nothing to compare against either —
    # comparing a version with itself would produce a reassuring identical pair that says
    # nothing.
    if promoted is None or int(promoted["version_number"]) == int(candidate["version_number"]):
        return {
            "candidate": candidate_block,
            "current": None,
            "comparable": None,
            "note": (
                "There is no other promoted model version to compare against. The candidate's "
                "metrics are reported on their own."
            ),
        }

    current_spans = await _trained_on_span_count(session, schema, promoted["version_number"])
    current_block = {
        "version_number": int(promoted["version_number"]),
        "status": promoted["status"],
        "metrics": promoted.get("metrics") or {},
        "trained_on_span_count": current_spans,
        "training_job_id": promoted.get("training_job_id"),
        "created_at": promoted.get("created_at"),
    }

    comparable = dataset_sizes_comparable(candidate_spans, current_spans)
    if comparable is False:
        note = (
            "These two runs were trained on materially different dataset sizes "
            f"({candidate_spans} and {current_spans} confirmed spans). Their metrics are not "
            "directly comparable."
        )
    elif comparable is None:
        note = (
            "The dataset size of at least one of these runs was not recorded, so it cannot be "
            "established whether their metrics are directly comparable."
        )
    else:
        note = (
            "These two runs were trained on similar dataset sizes "
            f"({candidate_spans} and {current_spans} confirmed spans). Metrics from different "
            "runs still reflect different evaluation splits."
        )

    return {
        "candidate": candidate_block,
        "current": current_block,
        "comparable": comparable,
        "note": note,
    }
