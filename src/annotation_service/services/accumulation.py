"""How much reviewed material has accumulated since the current model was trained.

One query and a shape. This module reports a number and stops: nothing here — and nothing that
calls it — creates, enqueues, schedules, or notifies to start a training job. Change 6 owns that
decision and it is human-gated (design.md Non-Goals, verification.md Risk 5).

**What the figure counts.** Confirmed spans created by production review, attributed to the
model version that predicted them. A span whose prediction came from tenant model version 3 was
necessarily reviewed after version 3 was trained, so "spans predicted by the currently serving
version" *is* the delta since that version was trained — no separate clock is needed, and the
attribution is a recorded fact rather than a timestamp comparison that a re-promotion would
invalidate.

**What it excludes.** Two things, for different reasons:

* Spans from base-model predictions (ADR-008's version 0). They are reviewed normally and they
  are real training data, but they say nothing about whether retraining *this tenant's* model
  would help, so counting them would inflate the figure with material that cannot answer change
  6's question (design.md Decision 5). They are reported separately rather than dropped.
* Spans a training run has already consumed, via `span_training_consumption`. The training
  worker writes that table when a run *completes*
  (`training_service.services.consumed_spans`), which is what makes this figure a delta rather
  than a running total: without the writer it would be correct until the first retrain and
  wrong after every one. With the table empty the exclusion is a no-op, which is exactly right
  before the first retrain.

**What it is not.** Not a readiness measure. ADR-010 governs readiness, per entity type, at its
own threshold, and this figure is a different quantity answering a different question. Nothing
here imports that threshold, compares against it, or uses the word — see
`gateway/api/v1/training_readiness.py` for the readiness report, which is deliberately a
separate surface.
"""

from sqlalchemy import text

from src.shared.confidence_routing import is_base_model_version

# Reported alongside the figure so a caller cannot mistake it for readiness without ignoring a
# field that says so in words. Cheaper than hoping the field name carries the distinction.
FIGURE_KIND = "accumulation_since_training"


async def current_model_version(session, schema: str) -> str:
    """The tenant's serving version, or `"0"` for ADR-008's base-model fallback.

    Read from the tenant's own `model_versions` the way `extraction_service`'s worker fallback
    reads it, so accumulation is attributed to the same version string routing recorded.

    `COALESCE(version_number, version)` because `model_versions` carries both. `version` is the
    original column from `002`; `018` added `version_number`, backfilled it from `version`, and
    dropped `version`'s NOT NULL, and the training worker has written only `version_number`
    since. Reading `version` alone therefore returned NULL for every version this platform has
    actually trained, so the fallback below fired and reported a real tenant as base-model —
    which is also what `extraction_service`'s worker would have disagreed with, since it reads
    `version_number`. Coalescing reads whichever the row has and keeps the two ends agreeing
    about the same version string.
    """
    result = await session.execute(
        text(
            f"SELECT COALESCE(version_number, version) AS v FROM {schema}.model_versions "
            "WHERE status = 'promoted' "
            "ORDER BY COALESCE(version_number, version) DESC LIMIT 1"
        )
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return str(row[0])
    return "0"


async def eligible_overview(session, schema: str) -> dict:
    """Per source, the number of training-eligible units not yet consumed by a completed
    training run, plus the most recent eligibility timestamp for that source.

    A unit is a completed annotation task (`annotation_tasks.training_eligible_at`), an
    annotator-approved automated `large` batch (`prelabel_batches.annotator_review_status =
    'approved'`), or an import file with every type mapped (`annotation_imports`). "Not yet
    consumed" is `training_eligible_at` later than the most recent completed training run's
    `completed_at` (or there is no completed run) — coarse, but it never under-reports
    waiting work.

    A report only: nothing here enqueues, approves, or promotes.
    """
    last_run = await session.execute(
        text(
            f"SELECT MAX(completed_at) FROM {schema}.training_jobs WHERE status = 'completed'"
        )
    )
    cutoff = last_run.scalar()

    def _clause(col: str) -> str:
        return f"{col} IS NOT NULL" + ("" if cutoff is None else f" AND {col} > :cutoff")

    params = {} if cutoff is None else {"cutoff": cutoff}

    async def _count(table: str, col: str, extra: str = "") -> tuple[int, str | None]:
        res = await session.execute(
            text(
                f"SELECT COUNT(*), MAX({col}) FROM {schema}.{table} "
                f"WHERE {_clause(col)}{extra}"
            ),
            params,
        )
        row = res.fetchone()
        return int(row[0] or 0), (row[1].isoformat() if row[1] else None)

    manual_count, manual_at = await _count("annotation_tasks", "training_eligible_at")
    auto_count, auto_at = await _count(
        "prelabel_batches",
        "training_eligible_at",
        " AND annotator_review_status = 'approved'",
    )
    import_count, import_at = await _count("annotation_imports", "training_eligible_at")

    return {
        "manual": {"count": manual_count, "latest_at": manual_at},
        "automated": {"count": auto_count, "latest_at": auto_at},
        "import": {"count": import_count, "latest_at": import_at},
    }


async def accumulation_report(session, schema: str) -> dict:
    """Spans accumulated from production review against the serving model version.

    Returns the figure, the version it is attributed to, and the base-model count kept
    separately. A response that folded the two together would be the ADR-008 error this is
    written to avoid, and one that omitted the base-model count would hide reviewed work rather
    than classify it.
    """
    version = await current_model_version(session, schema)
    base_model = is_base_model_version(version)

    result = await session.execute(
        text(
            f"SELECT p.model_version, p.served_by_base_model, s.entity_type, "
            f"       (bp.span_id IS NOT NULL) AS from_batch, COUNT(*) "
            f"FROM {schema}.span_review_provenance p "
            f"JOIN {schema}.spans s ON s.id = p.span_id "
            f"LEFT JOIN {schema}.span_training_consumption c ON c.span_id = p.span_id "
            f"LEFT JOIN {schema}.span_batch_provenance bp ON bp.span_id = p.span_id "
            # Already trained on: not accumulation any more, by definition. Written by change
            # 6's `training_service.services.consumed_spans` when a run completes.
            "WHERE c.span_id IS NULL "
            "GROUP BY p.model_version, p.served_by_base_model, s.entity_type, from_batch"
        )
    )
    rows = result.fetchall()

    accumulated = 0
    from_base_model = 0
    # A span promoted from an accepted automated batch has a `span_batch_provenance` row;
    # every other confirmed span is a manual (workspace / review-queue) span. The split is
    # over the same set the figure counts, so the two sum to it.
    by_source = {"manual": 0, "automated": 0}
    # Grouped by entity type as well as by version because a total says nothing about whether
    # the new evidence is concentrated in one type or spread across all of them, and that
    # distinction changes the retrain answer (proposal Open Questions, tasks.md 1.5). Only the
    # serving version's types appear: base-model spans are counted separately, and folding them
    # into a per-type figure would put material that cannot answer the question into the
    # breakdown that exists to answer it.
    by_entity_type: dict[str, int] = {}
    for model_version, served_by_base_model, entity_type, from_batch, count in rows:
        if served_by_base_model:
            from_base_model += count
        elif str(model_version) == version:
            accumulated += count
            by_entity_type[entity_type] = by_entity_type.get(entity_type, 0) + count
            by_source["automated" if from_batch else "manual"] += count

    return {
        # Ordered largest first: the type with the most new evidence is the one the decision
        # turns on, and a reader should not have to sort a dict to find it.
        "by_entity_type": (
            {}
            if base_model
            else dict(sorted(by_entity_type.items(), key=lambda kv: (-kv[1], kv[0])))
        ),
        "kind": FIGURE_KIND,
        # `None` rather than `"0"` when the base model is serving: there is no tenant-trained
        # version for the figure to be a delta against, and reporting `0` as the version would
        # invite it being read as one.
        "model_version": None if base_model else version,
        "spans_accumulated": 0 if base_model else accumulated,
        # manual + automated == spans_accumulated. Imports are not confirmed spans and are
        # not represented here — see `eligible_overview` for the import count.
        "by_source": {"manual": 0, "automated": 0} if base_model else by_source,
        # Recorded distinctly, never added in (ADR-008, design.md Decision 5).
        "spans_from_base_model": from_base_model,
        "note": (
            "Spans created by production review since this model version was trained. "
            "This is not a dataset readiness measure and is not comparable to the "
            "per-entity-type readiness threshold."
        ),
    }
