"""The profile status model and its permitted transitions.

`validated` exists so activation cannot precede a readiness check. `error` exists so an
unresolvable reference degrades one tenant's configuration rather than an unrelated
request path. `retired` is terminal.
"""

STATUS_DRAFT = "draft"
STATUS_VALIDATED = "validated"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_ERROR = "error"
STATUS_RETIRED = "retired"

STATUSES = (
    STATUS_DRAFT,
    STATUS_VALIDATED,
    STATUS_ACTIVE,
    STATUS_PAUSED,
    STATUS_ERROR,
    STATUS_RETIRED,
)

# Every transition the model permits, and no other. Notably absent: draft → active
# (activation must pass through validation) and error → active (recovery is only through
# revalidation). `retired` has no outgoing edge.
PERMITTED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_DRAFT: frozenset({STATUS_VALIDATED, STATUS_RETIRED}),
    STATUS_VALIDATED: frozenset({STATUS_ACTIVE, STATUS_ERROR, STATUS_RETIRED}),
    STATUS_ACTIVE: frozenset({STATUS_PAUSED, STATUS_ERROR, STATUS_RETIRED}),
    STATUS_PAUSED: frozenset({STATUS_ACTIVE, STATUS_RETIRED}),
    STATUS_ERROR: frozenset({STATUS_VALIDATED, STATUS_RETIRED}),
    STATUS_RETIRED: frozenset(),
}


class TransitionRejected(Exception):
    def __init__(self, current: str, requested: str, reason: str | None = None):
        self.current = current
        self.requested = requested
        self.reason = reason
        detail = f"'{current}' → '{requested}' is not a permitted profile transition"
        if reason:
            detail = f"{detail}: {reason}"
        super().__init__(detail)


def assert_transition(current: str, requested: str) -> None:
    if requested not in PERMITTED_TRANSITIONS.get(current, frozenset()):
        raise TransitionRejected(current, requested)
