"""Pre-submission per-entity-type readiness report.

The information the annotator dashboard already computes, offered at the moment it can actually
change a decision: before a training job is submitted rather than after a GPU run has finished
and the model turns out to have learned almost nothing about the starved half of the schema.

Two things this deliberately does not do.

It does not define a threshold. `DATASET_READINESS_ENTITIES_PER_TYPE` is imported from
`dashboard`, where ADR-010 put it and where it is described in-code as the single source of
truth. A second constant here would recreate exactly the duplicate-threshold conflict ADR-010
was written to resolve (design.md Decision 5, verification.md Risk 5).

It does not gate anything. There is no code path from this module into training submission, and
none should be added: enforcement belongs to `NER_MIN_ENTITIES_PER_TYPE`, and the decision to
train belongs to the System Admin at approval time, where ADR-009 put it. This endpoint reports
and stops (verification.md Risk 6).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.gateway.api.v1.dashboard import (
    DATASET_READINESS_ENTITIES_PER_TYPE,
    _annotator_type_counts,
)
from src.gateway.dependencies import get_db, require_tenant_role, resolve_tenant_from_jwt
from src.shared.entity_views import schema_for_tenant

router = APIRouter(prefix="/api/v1/tenants/{tenant_slug}", tags=["training-readiness"])


@router.get("/training-readiness")
async def get_training_readiness(
    tenant_slug: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    """Per-entity-type confirmed entity counts against the per-type threshold.

    `_annotator_type_counts` is reused rather than re-queried: it already evaluates the union of
    the tenant's active entity definitions and the types present in confirmed spans, which is
    what keeps a configured-but-never-annotated type visible at zero instead of silently absent
    (ADR-010). Two queries answering the same question would be free to disagree, and the one a
    tenant reads before spending a GPU run should not be the one that drifted.

    No tenant-wide total appears in the response. `ready` is every type meeting the threshold,
    never a sum compared against anything: a thousand `institute` entities do not make up for
    five `person_name` ones, and a report that let them would be the exact defect the per-type
    threshold replaced.
    """
    type_counts = await _annotator_type_counts(db, schema_for_tenant(tenant_id), tenant_id)

    entity_types = [
        {
            "entity_type": entity_type,
            "count": count,
            "threshold": DATASET_READINESS_ENTITIES_PER_TYPE,
            "meets_threshold": count >= DATASET_READINESS_ENTITIES_PER_TYPE,
            "shortfall": max(DATASET_READINESS_ENTITIES_PER_TYPE - count, 0),
        }
        for entity_type, count in type_counts
    ]
    short = [
        entity_type for entity_type in entity_types if not entity_type["meets_threshold"]
    ]

    return {
        "threshold_per_entity_type": DATASET_READINESS_ENTITIES_PER_TYPE,
        "entity_types": entity_types,
        "shortfalling_entity_types": [
            {"entity_type": entity_type["entity_type"], "count": entity_type["count"]}
            for entity_type in short
        ],
        "ready": bool(entity_types) and not short,
        # Stated in the payload rather than left to the caller to know. A client that reads this
        # as a gate is reading it wrong, and the response says so.
        "advisory": True,
        "blocks_submission": False,
    }
