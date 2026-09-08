"""Persisting the confidence split for an extraction run.

This is the write half of confidence routing. It runs inside the extraction worker's per-document
transaction, over the entities that run already reconstructed — there is no second inference pass
and no call to model serving anywhere in this module (design.md Decision 2). The model version
arrives as an argument, captured from the serving response by the caller, rather than being
looked up here after the fact (ADR-003).

Routing operates on reconstructed entities, not word-level predictions (design.md Decision 9). A
queued item is therefore a whole BIO span with min-aggregated confidence and character offsets,
which is what a reviewer can actually judge and what a span created from it can actually be. The
caller passes the same list it stores as `document_entities`, so the queue and the extraction
store cannot disagree about what the run found.

Nothing here reads into a business-facing response. `routed_predictions` is a separate store that
extraction results, entity queries, the entity projection, analytics and chat retrieval do not
consult, which is what lets below-threshold predictions be retained without changing anything a
business consumer sees.

Nothing here creates, enqueues, or schedules a training job.
"""

import uuid

from sqlalchemy import text

from src.shared.confidence_routing import (
    is_base_model_version,
    is_below_business_threshold,
    route_prediction,
)


def purge_expired_predictions(conn, schema: str, max_age_days: int) -> int:
    """Delete routed predictions older than the retention bound, returning how many went.

    The other half of Decision 11's bound. A resolved prediction is deleted the moment its
    outcome is recorded; this covers the abandoned path, where a queue that outpaces its
    reviewers would otherwise grow without limit. Recorded outcomes are untouched — they carry
    their own copies of everything accumulation accounting needs, precisely so this cleanup
    cannot destroy the accounting.

    Called inline from the extraction run rather than from a scheduled job. The work is small and
    bounded, and a periodic task registration is a piece of machinery this change deliberately
    does not introduce.
    """
    if not max_age_days or max_age_days <= 0:
        return 0
    result = conn.execute(
        text(
            f"DELETE FROM {schema}.routed_predictions "
            "WHERE created_at < NOW() - make_interval(days => :days)"
        ),
        {"days": int(max_age_days)},
    )
    return result.rowcount or 0


def record_routed_predictions(
    conn,
    schema: str,
    run_id: str,
    document_id: str,
    entities,
    model_version,
    review_threshold: float,
    business_threshold: float,
) -> dict:
    """Write one `routed_predictions` row per reconstructed entity and report the split.

    `entities` are `NormalizedEntity` values from `reconstruct_entities`, after validity
    filtering and duplicate collapse — the same list the caller stores. An entity with no
    character offsets is skipped rather than stored with invented ones: it could never become a
    span, so queueing it would only ask a reviewer to judge something that cannot be acted on.
    """
    counts = {"accepted": 0, "queued": 0, "below_business_threshold": 0, "skipped": 0}
    served_by_base_model = is_base_model_version(model_version)

    for entity in entities:
        if entity.char_start is None or entity.char_end is None:
            counts["skipped"] += 1
            continue

        confidence = float(entity.confidence)
        disposition = route_prediction(confidence, review_threshold)
        below_business = is_below_business_threshold(confidence, business_threshold)

        conn.execute(
            text(
                f"INSERT INTO {schema}.routed_predictions "
                "(id, run_id, document_id, entity_type, value, confidence, char_start, "
                " char_end, model_version, served_by_base_model, below_business_threshold, "
                " disposition) "
                "VALUES (:id, :run_id, :document_id, :entity_type, :value, :confidence, "
                "        :char_start, :char_end, :model_version, :base_model, :below_business, "
                "        :disposition)"
            ),
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "document_id": document_id,
                "entity_type": entity.entity_type,
                "value": entity.entity_value,
                "confidence": confidence,
                "char_start": entity.char_start,
                "char_end": entity.char_end,
                "model_version": str(model_version) if model_version is not None else "0",
                "base_model": served_by_base_model,
                "below_business": below_business,
                "disposition": disposition,
            },
        )
        counts[disposition] += 1
        if below_business:
            counts["below_business_threshold"] += 1

    return counts
