"""Sync scheduling evaluation (CAP-3, ADR-012).

The beat scheduler evaluates every active Azure Blob connection every
15 minutes. `evaluate_connection` is a pure function of (active, last success,
now), so the cadence and the one missed-schedule catch-up are unit-testable
without a broker. Enqueueing itself goes through the Celery task in `tasks.py`.
"""

from datetime import datetime, timezone

# Mirrors the CAP-2 control-plane schedule contract (`schedule.cadence_minutes`).
SYNC_CADENCE_MINUTES = 15
# A connection whose last success is older than this many cadences missed at
# least one scheduled tick and gets exactly one catch-up run.
CATCHUP_AFTER_CADENCES = 2

DECISION_DUE = "due"
DECISION_CATCHUP = "catchup"
DECISION_NOT_DUE = "not_due"
DECISION_INACTIVE = "inactive"

DECISIONS = frozenset({DECISION_DUE, DECISION_CATCHUP, DECISION_NOT_DUE, DECISION_INACTIVE})


class ScheduleDecision:
    def __init__(self, decision: str, trigger: str | None = None):
        self.decision = decision
        self.trigger = trigger


def evaluate_connection(*, active: bool, last_success_at: datetime | None,
                        connected_at: datetime | None = None,
                        now: datetime | None = None) -> ScheduleDecision:
    """Decide whether a connection is due for a scheduled run or a catch-up."""
    from src.document_service.blob_sync.sync import (
        TRIGGER_CATCHUP,
        TRIGGER_SCHEDULED,
    )

    now = now or datetime.now(timezone.utc)

    def _age(ts):
        if ts is None:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds() / 60

    if not active:
        return ScheduleDecision(DECISION_INACTIVE)
    cadence = SYNC_CADENCE_MINUTES
    reference = last_success_at if last_success_at is not None else connected_at
    age = _age(reference)
    if age is None:
        return ScheduleDecision(DECISION_DUE, TRIGGER_SCHEDULED)
    if age >= CATCHUP_AFTER_CADENCES * cadence:
        return ScheduleDecision(DECISION_CATCHUP, TRIGGER_CATCHUP)
    if age >= cadence:
        return ScheduleDecision(DECISION_DUE, TRIGGER_SCHEDULED)
    return ScheduleDecision(DECISION_NOT_DUE)
