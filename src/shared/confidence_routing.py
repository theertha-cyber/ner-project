"""The confidence split, as pure functions.

Shared rather than owned by either service because the two ends of it live apart: the extraction
worker applies the split as it writes routed predictions, and `annotation_service` reads the
result to work the queue and to draw audit samples. Keeping the rule itself in one place is what
stops the two ends developing their own idea of where the boundary is.

Nothing here touches a database, calls a model, or decides anything beyond which side of a
threshold a number falls on. In particular, nothing here — or anywhere downstream of it —
creates, enqueues, or schedules a training job. Accumulation is reported and that is all; the
retraining decision belongs to a person (design.md Non-Goals).
"""

# Which side of the review threshold a prediction fell on.
#
# `accepted` means nobody will look at it unless an audit draw picks it up, which is exactly why
# the audit path exists (design.md Decision 6): it is otherwise the only path with no feedback at
# all, and a confidently wrong model is the hardest kind to notice.
DISPOSITION_ACCEPTED = "accepted"
DISPOSITION_QUEUED = "queued"

DISPOSITIONS = (DISPOSITION_ACCEPTED, DISPOSITION_QUEUED)

# What a reviewer, human or LLM, can conclude about a queued prediction. Both routes produce
# this same shape so that span creation and accumulation accounting never branch on who reviewed
# (design.md Decision 4).
OUTCOME_CONFIRMED = "confirmed"
OUTCOME_CORRECTED = "corrected"
OUTCOME_REJECTED = "rejected"

OUTCOMES = (OUTCOME_CONFIRMED, OUTCOME_CORRECTED, OUTCOME_REJECTED)

ROUTE_HUMAN = "human"
ROUTE_LLM = "llm"

ROUTES = (ROUTE_HUMAN, ROUTE_LLM)

# Only `confirmed` and `corrected` become training data. A rejection records that the model was
# wrong and stops there: writing an explicit `O` over the region would assert more than the
# reviewer actually checked — they rejected *this type at these offsets*, not every type over
# that span — and would reintroduce change 1's partial-labeling problem (design.md Decision 12).
SPAN_PRODUCING_OUTCOMES = (OUTCOME_CONFIRMED, OUTCOME_CORRECTED)

# ADR-008's fallback: a tenant with no active trained model is served by the base model, which
# reports itself as version 0. Predictions it produced are routed and reviewed like any other,
# but they say nothing about whether retraining *this tenant's* model would help, so they are
# recorded distinctly and excluded from the accumulation figure (design.md Decision 5).
BASE_MODEL_VERSION = "0"


def is_base_model_version(model_version) -> bool:
    """Whether `model_version` is ADR-008's base-model fallback rather than a tenant-trained
    version. A missing version is treated as the base model: the fallback is what serves when
    nothing has been trained, so an absent version is that case, not a tenant one."""
    if model_version is None:
        return True
    return str(model_version).strip() in ("", BASE_MODEL_VERSION)


def route_prediction(confidence: float, review_threshold: float) -> str:
    """Which side of the review threshold this prediction falls on.

    At or above the threshold is auto-accepted; below it is queued. The boundary is inclusive on
    the accept side to match the spec's wording ("a prediction at or above the review threshold
    SHALL be auto-accepted"), so a threshold of 0.90 and a prediction of exactly 0.90 is not
    review work.

    `confidence` is expected to be the span-level figure `aggregate_confidence` produces — the
    minimum across the span's constituent tokens (design.md Decision 8). This function does not
    re-derive it: routing and the extraction store must not disagree about the same span's
    confidence, and they cannot if only one of them computes it.
    """
    return DISPOSITION_ACCEPTED if confidence >= review_threshold else DISPOSITION_QUEUED


def is_below_business_threshold(confidence: float, business_threshold: float) -> bool:
    """Whether this prediction is excluded from business-facing extraction results.

    A separate question from `route_prediction`, deliberately (design.md Decision 1). Both are
    recorded on the routed prediction so that moving the review threshold cannot change what a
    business consumer sees, and lowering the business threshold cannot change review volume.
    """
    return confidence < business_threshold


def resolve_review_policy(tenant_policy, default_policy: str) -> str:
    """The route that resolves this tenant's queued predictions.

    A tenant with no recorded policy falls back to the configured default, which ships as
    `human`. An unrecognised stored value also falls back rather than raising: the failure mode
    of a typo in a settings row should be "a person reviews it", never "the LLM reviews it" or
    "the queue stops" (design.md Decision 10).
    """
    if tenant_policy in ROUTES:
        return tenant_policy
    return default_policy if default_policy in ROUTES else ROUTE_HUMAN
