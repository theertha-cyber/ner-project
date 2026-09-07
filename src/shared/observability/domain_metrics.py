"""Every domain metric family this platform emits, declared in one place.

The foundation change shipped RED metrics derived from the ASGI layer: request rate,
error count, duration. Nothing in them says what the platform *does*. This module holds
the families that do — the SQL repair loop, guardrail decisions, extraction stages,
inference paths, training lifecycle — plus the four tenant-safety counters Exit Gate 3
names.

Why a declaration module rather than `create_counter` where the measurement happens
(design Decision 1):

- The tenant-label allowlist is not enforceable without a place to enumerate. A test can
  only assert "no family outside the list carries `tenant_id`" if the set of families is
  reachable by import, not by running every code path that might create one.
- Cardinality is controlled by the label's *value* set, not by the family count. An
  unbounded value is the failure mode, so every label declares a closed set and the
  recorder coerces anything outside it to `other` rather than minting a new series.
- Redaction has one review surface. Fifty scattered `create_counter` calls are fifty
  places a `filename:<literal>` drawn from a tenant document can become a Prometheus
  label, where retention is long, access is broad, and the foundation's log redaction
  filter does not apply at all.

Label values are the measured code's own constants wherever the measured code has them
(design Decision 2). `SQLAttemptOutcome`, the entity-resolver outcomes and the guardrail
rule identifiers are imported, not restated, so a rename upstream is an ImportError here
rather than a stale label value that silently matches no dashboard.

Both metric backends are written on every record. A FastAPI service has a
`prometheus_client` registry scraped at `/metrics` and no OTel meter provider; the two
Celery workers have a meter provider exporting over OTLP and no scrape endpoint. Exactly
one of the two is live in any given process, and the other is a no-op, so the double
write costs an attribute lookup and removes the need for every call site to know which
kind of process it is running in.
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

# Imported, never restated — a rename upstream must break this import rather than leave a
# label value that no longer matches anything the code emits (task 1.2, design Decision 2).
from src.chat_api.services.entity_resolver import AMBIGUOUS, OVER_CAP, UNIQUE, UNRESOLVED
from src.chat_api.services.guardrails import GUARDRAIL_RULES
from src.chat_api.services.sql_generator import (
    DEFECT_CLASSES,
    SQLAttemptOutcome,
    _defect_class,
)

logger = logging.getLogger(__name__)

# The value a recorder substitutes when a caller passes something outside a label's
# declared set. Present in every enumeration, so the set stays closed and a coercion is
# visible on the dashboard rather than silently dropped.
OTHER = "other"
NONE = "none"

TRUE_FALSE = frozenset({"true", "false"})


# --------------------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Label:
    """One label key and the closed set of values it may carry.

    `values` is required and must be non-empty: the point of the declaration is that the
    series count for a family is the product of its label enumerations and is therefore
    computable before shipping, not discovered when the endpoint gets slow.
    """

    name: str
    values: frozenset[str]

    def coerce(self, value) -> str:
        if value is None:
            rendered = NONE
        else:
            rendered = str(value)
        if rendered in self.values:
            return rendered
        # Not an exception: a metric must never be able to fail the work it measures. The
        # series lands under `other`, which is itself declared, so cardinality holds.
        logger.debug(
            "metric_label_value_coerced",
            extra={"label": self.name, "declared": len(self.values)},
        )
        return OTHER if OTHER in self.values else sorted(self.values)[0]


@dataclass(frozen=True)
class Family:
    """One metric family: its name, kind, help text and exact labels."""

    name: str
    kind: str  # "counter" | "histogram" | "gauge"
    description: str
    labels: tuple[Label, ...] = ()
    buckets: tuple[float, ...] | None = None

    @property
    def label_names(self) -> tuple[str, ...]:
        return tuple(label.name for label in self.labels)

    def series_count(self) -> int:
        total = 1
        for label in self.labels:
            total *= len(label.values)
        return total


# Reused label declarations. Defined once so a family cannot drift from its neighbour on
# what "outcome" or "queue" means.

_TENANT = Label("tenant_id", frozenset())  # sentinel; see `_TenantLabel` below


class _TenantLabel(Label):
    """`tenant_id` is the one label whose value set is genuinely open.

    It is enumerable only in the sense that it is bounded by the tenant table, and it is
    therefore permitted on exactly the five families named in `TENANT_LABEL_ALLOWLIST` —
    per-tenant consumption attribution, which is what Exit Gate 3 means by attribution and
    what billing will eventually read. `coerce` passes the value through unchanged, and
    the enumeration test skips this label by identity rather than by name.
    """

    def __init__(self) -> None:
        super().__init__("tenant_id", frozenset({"<tenant>"}))

    def coerce(self, value) -> str:
        return str(value) if value is not None else "unknown"


def tenant_label() -> Label:
    return _TenantLabel()


# Exception class names are `type(e).__name__` per design Decision 2, but an unbounded
# label value is the cardinality failure mode this module exists to prevent. So the set is
# the classes these paths are actually known to raise, and anything else lands on `other`
# — the class name still reaches the log record and the span, where it is not a series.
ERROR_CLASSES = frozenset({
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "RuntimeError",
    "TimeoutError",
    "ConnectionError",
    "OSError",
    "MemoryError",
    "CancelledError",
    "ProgrammingError",
    "OperationalError",
    "IntegrityError",
    "DataError",
    "DBAPIError",
    "StatementError",
    "SQLAlchemyError",
    "HTTPException",
    "APIError",
    "APIConnectionError",
    "APITimeoutError",
    "APIStatusError",
    "RateLimitError",
    "AuthenticationError",
    "BadRequestError",
    "InternalServerError",
    "PermissionDeniedError",
    "NotFoundError",
    "SQLGenerationFailed",
    "OnnxRuntimeError",
    "Retry",
    "SoftTimeLimitExceeded",
    "WorkerLostError",
    OTHER,
})


# The nine sites that interpolate a schema name into `SET search_path TO {schema}`. Named
# rather than free-form so a violation counter's label cannot itself become the unbounded
# value (task 2.3, design Decision 5).
SEARCH_PATH_CALL_SITES = frozenset({
    "chat_api.sql_generator.execute_sql",
    "chat_api.sql_generator.sample_values",
    "chat_api.sql_generator.relation_values",
    "chat_api.sql_generator.filename_probe",
    "chat_api.sql_generator.wrong_relation_probe",
    "analytics_service.dependencies.get_session",
    "analytics_service.worker.session",
    "extraction_service.dependencies.get_session",
    "shared.tenant_context.get_session",
    OTHER,
})

AUTH_FAILURE_REASONS = frozenset({
    "missing_header",
    "malformed_token",
    "expired_token",
    "invalid_signature",
    "invalid_claims",
    OTHER,
})

# Both queues the platform configures, under the names the broker actually uses.
# `extraction` comes from `settings.extraction_celery_queue`; training never sets
# `task_default_queue`, so its tasks land on Celery's own default, which is `celery`.
# Named here as it really is rather than as it ought to be — a label that does not match
# the broker key is a dashboard that reads zero forever.
CELERY_QUEUES = frozenset({"extraction", "celery", OTHER})

# The graph's node names, verbatim from the registry `build_nodes` returns. Verbatim
# because the stage label has to be the thing an engineer reading a trace already knows
# the name of; a parallel vocabulary would need translating at every dashboard.
CHAT_STAGES = frozenset({
    "guardrail",
    "orchestrator",
    "entity_resolution",
    "retrieval_execution",
    "source_assembly",
    "prompt_assembly",
    "generation",
    OTHER,
})

# The registered capability names, verbatim from `src/shared/retrieval/tools/`. Two today;
# `catalogue_slice` is the grounding read in `sql_generator`, which is not a registered
# tool but is measured on the same family because it is the same kind of work.
RETRIEVAL_CAPABILITIES = frozenset({
    "structured_retrieval",
    "semantic_retrieval",
    "catalogue_slice",
    OTHER,
})

EXTRACTION_STAGES = frozenset({
    "download",
    "parse",
    "chunk",
    "inference",
    "postprocess",
    "projection",
    "persist",
    OTHER,
})

LLM_OPERATIONS = frozenset({
    "domain_classification",
    "sql_generation",
    "answer_generation",
    "entity_selection",
    "rag_orchestration",
    "entity_postprocess",
    OTHER,
})

TRAINING_STATES = frozenset({
    "queued",
    "running",
    "evaluating",
    "completed",
    "failed",
    "cancelled",
    OTHER,
})

TRAINING_FAILURE_CAUSES = frozenset({
    "dataset_insufficient",
    "training_error",
    "evaluation_error",
    "export_error",
    "timeout",
    "cancelled",
    OTHER,
})

# ADR-008: the base model answering is a success, not a fallback failure. The two ways of
# reaching it are kept apart, because "no promoted model yet" and "the tenant's model
# raised" are different operational facts (task 6.2).
INFERENCE_PATHS = frozenset({
    "tenant_onnx",
    "base_model_no_promoted",
    "base_model_error_fallback",
    OTHER,
})

_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
_LONG_DURATION_BUCKETS = (1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0)
_COUNT_BUCKETS = (0.0, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 1000.0)
_SMALL_COUNT_BUCKETS = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0)
_UNIT_BUCKETS = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0)


FAMILIES: dict[str, Family] = {}


def _declare(family: Family) -> Family:
    if family.name in FAMILIES:
        raise ValueError(f"metric family declared twice: {family.name}")
    for label in family.labels:
        if not label.values:
            raise ValueError(
                f"{family.name}: label {label.name!r} declares no values — the series "
                "count must be computable before shipping"
            )
    FAMILIES[family.name] = family
    return family


# --- Tenant safety (section 2) ---------------------------------------------------------

TENANT_MISMATCH = _declare(Family(
    "ner_tenant_mismatch_total",
    "counter",
    "Requests rejected because the token's tenant differed from the addressed tenant. "
    "Non-zero means an attempted cross-tenant access, not an ordinary permission denial.",
))

SEARCH_PATH_VIOLATIONS = _declare(Family(
    "ner_search_path_violations_total",
    "counter",
    "Schema names that failed the tenant-schema pattern immediately before being "
    "interpolated into SET search_path.",
    labels=(Label("code_path", SEARCH_PATH_CALL_SITES),),
))

AUTH_FAILURES = _declare(Family(
    "ner_auth_failures_total",
    "counter",
    "Authentication rejections by enumerated reason. No token value or fragment is ever "
    "a label.",
    labels=(Label("reason", AUTH_FAILURE_REASONS),),
))

RATE_LIMIT_REJECTIONS = _declare(Family(
    "ner_rate_limit_rejections_total",
    "counter",
    "Callers rejected for exceeding their configured rate limit.",
    labels=(tenant_label(), Label("scope", frozenset({"internal", "widget", OTHER}))),
))

# --- Guardrails, resolution, retrieval (section 3) --------------------------------------

GUARDRAIL_DECISIONS = _declare(Family(
    "ner_guardrail_decisions_total",
    "counter",
    "Guardrail decisions by rule and outcome.",
    labels=(
        Label("rule", frozenset(GUARDRAIL_RULES) | {OTHER}),
        Label("decision", frozenset({"blocked", "admitted", "fallback", OTHER})),
    ),
))

GUARDRAIL_FAIL_OPEN = _declare(Family(
    "ner_guardrail_fail_open_total",
    "counter",
    "Guardrail admissions caused by a classifier error rather than by an in-domain "
    "verdict. Deliberately separate from the admit counter so a degrading security "
    "control cannot hide inside a normal admission.",
    labels=(Label("error_class", ERROR_CLASSES),),
))

GUARDRAIL_CLASSIFIER_SPLIT = _declare(Family(
    "ner_guardrail_classifier_split_total",
    "counter",
    "Domain classifications where the with-history and bare views disagreed and the "
    "query was admitted.",
))

ENTITY_RESOLUTIONS = _declare(Family(
    "ner_entity_resolutions_total",
    "counter",
    "Entity-resolution outcomes. No mention text is recorded anywhere.",
    labels=(Label("outcome", frozenset({UNRESOLVED, UNIQUE, AMBIGUOUS, OVER_CAP, OTHER})),),
))

ENTITY_RESOLUTION_MENTIONS = _declare(Family(
    "ner_entity_resolution_mentions_checked",
    "histogram",
    "Mentions examined per resolution attempt.",
    labels=(Label("outcome", frozenset({UNRESOLVED, UNIQUE, AMBIGUOUS, OVER_CAP, OTHER})),),
    buckets=_SMALL_COUNT_BUCKETS,
))

RETRIEVAL_RESULTS = _declare(Family(
    "ner_retrieval_results",
    "histogram",
    "Results returned per retrieval, by capability.",
    labels=(Label("capability", RETRIEVAL_CAPABILITIES),),
    buckets=_COUNT_BUCKETS,
))

RETRIEVAL_ZERO_RESULTS = _declare(Family(
    "ner_retrieval_zero_results_total",
    "counter",
    "Retrievals that returned nothing. A zero-result rate is the signal a duration "
    "histogram cannot show.",
    labels=(Label("capability", RETRIEVAL_CAPABILITIES),),
))

RETRIEVAL_HIT_RATE = _declare(Family(
    "ner_retrieval_hit_rate",
    "histogram",
    "Fraction of a retrieval's results that survived into the answer's sources.",
    labels=(Label("capability", RETRIEVAL_CAPABILITIES),),
    buckets=_UNIT_BUCKETS,
))

RERANK_DURATION = _declare(Family(
    "ner_rerank_duration_seconds",
    "histogram",
    "Time spent reranking retrieved passages.",
    buckets=_DURATION_BUCKETS,
))

# --- SQL generation, execution, LLM usage (section 4) ------------------------------------

_SQL_OUTCOMES = frozenset({
    SQLAttemptOutcome.SUCCESS,
    SQLAttemptOutcome.GENERATION_ERROR,
    SQLAttemptOutcome.VALIDATION_ERROR,
    SQLAttemptOutcome.EXECUTION_ERROR,
    SQLAttemptOutcome.EMPTY_WITH_DEFECT,
    OTHER,
})

SQL_ATTEMPTS = _declare(Family(
    "ner_sql_attempts_total",
    "counter",
    "Individual generate/validate/execute attempts by outcome and defect class. The "
    "defect *class* only: SQLAttempt.defect carries filename and relation literals drawn "
    "from tenant documents, and a metric label is not redacted anywhere.",
    labels=(
        Label("outcome", _SQL_OUTCOMES),
        Label("defect_class", frozenset(DEFECT_CLASSES) | {NONE, OTHER}),
    ),
))

SQL_REPAIR_DEPTH = _declare(Family(
    "ner_sql_repair_depth",
    "histogram",
    "Repairs performed per completed generation — attempts minus one. This is the Phase 1 "
    "repair-loop claim as a measured quantity.",
    buckets=_SMALL_COUNT_BUCKETS,
))

SQL_GENERATIONS = _declare(Family(
    "ner_sql_generations_total",
    "counter",
    "Completed SQL generations by outcome, with the abandon reason where one applies.",
    labels=(
        Label("outcome", frozenset({"succeeded", "abandoned", OTHER})),
        Label("abandon_reason", frozenset({
            NONE,
            "attempts_exhausted",
            "deadline_exhausted",
            "no_relational_coverage",
            OTHER,
        })),
    ),
))

SQL_EXECUTION_DURATION = _declare(Family(
    "ner_sql_execution_duration_seconds",
    "histogram",
    "Wall time of an executed generated statement.",
    buckets=_DURATION_BUCKETS,
))

SQL_EXECUTION_ROWS = _declare(Family(
    "ner_sql_execution_rows",
    "histogram",
    "Rows returned by an executed generated statement.",
    buckets=_COUNT_BUCKETS,
))

SQL_EXECUTIONS = _declare(Family(
    "ner_sql_executions_total",
    "counter",
    "Executed generated statements, and whether the row set hit the result cap.",
    labels=(Label("truncated", TRUE_FALSE),),
))

LLM_CALLS = _declare(Family(
    "ner_llm_calls_total",
    "counter",
    "LLM provider calls by operation and outcome. On failure the label is an enumerated "
    "error class, never the provider's message text.",
    labels=(
        Label("operation", LLM_OPERATIONS),
        Label("outcome", frozenset({"success", "error", OTHER})),
        Label("error_class", ERROR_CLASSES | {NONE}),
    ),
))

LLM_TOKENS = _declare(Family(
    "ner_llm_tokens_total",
    "counter",
    "Tokens consumed, by direction. Tenant-labelled: this is the consumption attribution "
    "Exit Gate 3 names and billing will read.",
    labels=(
        tenant_label(),
        Label("operation", LLM_OPERATIONS),
        Label("direction", frozenset({"input", "output"})),
    ),
))

LLM_COST = _declare(Family(
    "ner_llm_cost_usd_total",
    "counter",
    "Estimated provider spend in USD. Tenant-labelled for the same reason as tokens.",
    labels=(tenant_label(), Label("operation", LLM_OPERATIONS)),
))

LLM_DURATION = _declare(Family(
    "ner_llm_duration_seconds",
    "histogram",
    "Provider latency for one LLM call, measured at the call site rather than inferred "
    "from the enclosing stage.",
    labels=(Label("operation", LLM_OPERATIONS),),
    buckets=_DURATION_BUCKETS,
))

ANSWER_CONFIDENCE = _declare(Family(
    "ner_answer_confidence",
    "histogram",
    "Confidence attached to a composed answer.",
    buckets=_UNIT_BUCKETS,
))

ANSWER_CITATIONS = _declare(Family(
    "ner_answer_citations",
    "histogram",
    "Citations attached to a composed answer. ADR-007's citation enforcement becomes "
    "counted rather than merely executed.",
    buckets=_SMALL_COUNT_BUCKETS,
))

ANSWERS = _declare(Family(
    "ner_answers_total",
    "counter",
    "Composed answers, and whether the reply was hedged.",
    labels=(Label("hedged", TRUE_FALSE),),
))

CHAT_REQUESTS = _declare(Family(
    "ner_chat_requests_total",
    "counter",
    "Chat requests by outcome. Tenant-labelled for per-tenant consumption attribution.",
    labels=(
        tenant_label(),
        Label("outcome", frozenset({"answered", "declined", "clarification", "failed", OTHER})),
    ),
))

CHAT_STAGE_DURATION = _declare(Family(
    "ner_chat_stage_duration_seconds",
    "histogram",
    "Time in one graph stage. The stage breakdown is what makes an ADR-007 P95 breach "
    "diagnosable rather than merely visible.",
    labels=(Label("stage", CHAT_STAGES),),
    buckets=_DURATION_BUCKETS,
))

# --- Extraction, projection, queues (section 5) ------------------------------------------

EXTRACTION_JOBS = _declare(Family(
    "ner_extraction_jobs_total",
    "counter",
    "Extraction runs by outcome. Tenant-labelled for consumption attribution.",
    labels=(
        tenant_label(),
        Label("outcome", frozenset({"succeeded", "partial", "failed", OTHER})),
    ),
))

EXTRACTION_STAGE_DURATION = _declare(Family(
    "ner_extraction_stage_duration_seconds",
    "histogram",
    "Time in one extraction stage.",
    labels=(Label("stage", EXTRACTION_STAGES),),
    buckets=_LONG_DURATION_BUCKETS,
))

EXTRACTION_STAGE_REACHED = _declare(Family(
    "ner_extraction_stage_reached_total",
    "counter",
    "Furthest extraction stage a run reached, which is how a failed run is located "
    "without reading its logs.",
    labels=(Label("stage", EXTRACTION_STAGES),),
))

EXTRACTION_RETRIES = _declare(Family(
    "ner_extraction_retries_total",
    "counter",
    "Retries performed within an extraction run.",
))

EXTRACTION_PARTIAL_FAILURES = _declare(Family(
    "ner_extraction_partial_failures_total",
    "counter",
    "Units within a run that failed while the run as a whole continued.",
    labels=(Label("stage", EXTRACTION_STAGES),),
))

EXTRACTION_PAGES = _declare(Family(
    "ner_extraction_pages_processed",
    "histogram",
    "Pages processed per extraction run.",
    buckets=_COUNT_BUCKETS,
))

EXTRACTION_ENTITIES = _declare(Family(
    "ner_extraction_entities_total",
    "counter",
    "Entities extracted, in aggregate. Deliberately carries no entity-type label: entity "
    "types are tenant-configured, so the value set is neither enumerable at declaration "
    "nor safe in a store shared across tenants — a tenant that configures "
    "`policy_holder` and `claim_number` is identifiable from label values alone. "
    "ADR-010's per-type granularity lives on the run's span, which is tenant-scoped and "
    "covered by the release-gate scan. See design Decision 12.",
))

EXTRACTION_FAILURES = _declare(Family(
    "ner_extraction_failures_total",
    "counter",
    "Extraction runs that raised, by exception class.",
    labels=(Label("error_class", ERROR_CLASSES),),
))

PROJECTION_DURATION = _declare(Family(
    "ner_projection_duration_seconds",
    "histogram",
    "Time to project extracted entities into the relational surface.",
    buckets=_LONG_DURATION_BUCKETS,
))

PROJECTIONS = _declare(Family(
    "ner_projections_total",
    "counter",
    "Projections, and whether source and projected row counts agreed.",
    labels=(Label("drift", frozenset({"clean", "row_count_mismatch", OTHER})),),
))

CELERY_QUEUE_DEPTH = _declare(Family(
    "ner_celery_queue_depth",
    "gauge",
    "Messages waiting on a queue, read from the broker at scrape time. Registered on the "
    "producer side only: depth is a property of the queue, and every worker reporting it "
    "would produce N identical series differing by instance alone.",
    labels=(Label("queue", CELERY_QUEUES),),
))

CELERY_TASK_WAIT = _declare(Family(
    "ner_celery_task_wait_seconds",
    "histogram",
    "Time a task spent enqueued, computed against the enqueue timestamp stamped on the "
    "message header.",
    labels=(Label("queue", CELERY_QUEUES),),
    buckets=_LONG_DURATION_BUCKETS,
))

CELERY_CLOCK_SKEW = _declare(Family(
    "ner_celery_clock_skew_total",
    "counter",
    "Wait-time computations that came out negative and were clamped to zero. Skew "
    "becomes visible rather than silently distorting the wait histogram.",
    labels=(Label("queue", CELERY_QUEUES),),
))

CELERY_TASK_DURATION = _declare(Family(
    "ner_celery_task_duration_seconds",
    "histogram",
    "Task execution time, measured in the worker where the task actually runs.",
    labels=(Label("queue", CELERY_QUEUES),),
    buckets=_LONG_DURATION_BUCKETS,
))

CELERY_TASK_RETRIES = _declare(Family(
    "ner_celery_task_retries_total",
    "counter",
    "Task retries.",
    labels=(Label("queue", CELERY_QUEUES),),
))

CELERY_TASK_FAILURES = _declare(Family(
    "ner_celery_task_failures_total",
    "counter",
    "Tasks that raised, by exception class. No message text is ever a label.",
    labels=(Label("queue", CELERY_QUEUES), Label("error_class", ERROR_CLASSES)),
))

CELERY_WORKER_UP = _declare(Family(
    "ner_celery_worker_up",
    "gauge",
    "1 while a worker for this queue is consuming, 0 once it has stopped.",
    labels=(Label("queue", CELERY_QUEUES),),
))

# --- Model serving and training (section 6) -----------------------------------------------

INFERENCE_DURATION = _declare(Family(
    "ner_inference_duration_seconds",
    "histogram",
    "Inference wall time by serving path.",
    labels=(Label("path", INFERENCE_PATHS),),
    buckets=_DURATION_BUCKETS,
))

INFERENCES = _declare(Family(
    "ner_inferences_total",
    "counter",
    "Inferences by serving path and outcome. Under ADR-008 the base-model path is a "
    "success, not a failure — which is why the path and the outcome are separate labels.",
    labels=(
        Label("path", INFERENCE_PATHS),
        Label("outcome", frozenset({"success", "error", OTHER})),
    ),
))

INFERENCE_WINDOWS = _declare(Family(
    "ner_inference_windows",
    "histogram",
    "Sliding windows built for one inference request.",
    buckets=_COUNT_BUCKETS,
))

INFERENCE_BATCH_SIZE = _declare(Family(
    "ner_inference_batch_size",
    "histogram",
    "Windows submitted to the model in one batch.",
    buckets=_COUNT_BUCKETS,
))

MODEL_LOAD_DURATION = _declare(Family(
    "ner_model_load_duration_seconds",
    "histogram",
    "Time to make a tenant's model ready to serve.",
    labels=(Label("result", frozenset({"cold_start", "cache_hit", OTHER})),),
    buckets=_LONG_DURATION_BUCKETS,
))

MODEL_LOADS = _declare(Family(
    "ner_model_loads_total",
    "counter",
    "Model-load events, separating a cold start from a cache hit.",
    labels=(Label("result", frozenset({"cold_start", "cache_hit", OTHER})),),
))

TRAINING_TRANSITIONS = _declare(Family(
    "ner_training_job_transitions_total",
    "counter",
    "Training job state transitions. Job identity derives from the approved "
    "`training_jobs` row, per ADR-009, never from a request payload.",
    labels=(Label("state", TRAINING_STATES),),
))

TRAINING_DURATION = _declare(Family(
    "ner_training_job_duration_seconds",
    "histogram",
    "Total wall time of a training job.",
    labels=(Label("final_state", TRAINING_STATES),),
    buckets=_LONG_DURATION_BUCKETS,
))

TRAINING_EPOCHS = _declare(Family(
    "ner_training_epochs_completed",
    "histogram",
    "Epochs completed per job — progress, not model quality.",
    buckets=_SMALL_COUNT_BUCKETS,
))

TRAINING_FAILURES = _declare(Family(
    "ner_training_job_failures_total",
    "counter",
    "Training jobs that failed, by enumerated cause. Model *quality* — F1, precision, "
    "recall, loss — is deliberately absent from every family here: MLflow versions those "
    "against the run, the params and the artifact, and a mirror in Prometheus would be a "
    "second source of truth with worse fidelity and a shorter retention window. See "
    "design Decision 9.",
    labels=(Label("cause", TRAINING_FAILURE_CAUSES),),
))


# --------------------------------------------------------------------------------------
# The tenant-label allowlist
# --------------------------------------------------------------------------------------

# Five families, written out. Not a prefix, not a pattern, not a wildcard: `ner_llm_*`
# would admit families nobody reviewed, which is the same mistake at one remove. Growing
# this list is a diff, which is the point — every other question a tenant label could
# answer is answerable by joining a trace, where `tenant_id` already lives and access is
# narrower. See design Decision 10.
TENANT_LABEL_ALLOWLIST: frozenset[str] = frozenset({
    "ner_chat_requests_total",
    "ner_llm_tokens_total",
    "ner_llm_cost_usd_total",
    "ner_extraction_jobs_total",
    "ner_rate_limit_rejections_total",
})


def families_carrying_tenant_label() -> frozenset[str]:
    """Every declared family whose label set includes `tenant_id`."""
    return frozenset(
        name for name, family in FAMILIES.items() if "tenant_id" in family.label_names
    )


def allowlist_violations() -> list[str]:
    """Declared families carrying `tenant_id` that the allowlist does not name."""
    return sorted(families_carrying_tenant_label() - TENANT_LABEL_ALLOWLIST)


# --------------------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------------------

_prom_instruments: dict[str, object] = {}
_otel_instruments: dict[str, object] = {}


def _prom(family: Family):
    """The `prometheus_client` instrument for a family, created on first use.

    Created lazily rather than at import: the module is imported by processes that never
    record anything from it, and a registration collision at import time would take a
    service down over a metric.
    """
    instrument = _prom_instruments.get(family.name)
    if instrument is not None:
        return instrument
    try:
        if family.kind == "counter":
            # `prometheus_client` appends `_total` itself, so a declared name already
            # ending in it would expose `..._total_total`.
            base = family.name[: -len("_total")] if family.name.endswith("_total") else family.name
            instrument = Counter(base, family.description, family.label_names)
        elif family.kind == "histogram":
            instrument = Histogram(
                family.name, family.description, family.label_names,
                buckets=family.buckets or Histogram.DEFAULT_BUCKETS,
            )
        else:
            instrument = Gauge(family.name, family.description, family.label_names)
    except ValueError:
        # Already registered — a re-import under a test runner, or two processes sharing
        # an interpreter. Reuse rather than fail.
        instrument = REGISTRY._names_to_collectors.get(family.name)  # noqa: SLF001
        if instrument is None:
            logger.debug("metric_instrument_unavailable", extra={"family": family.name})
            return None
    _prom_instruments[family.name] = instrument
    return instrument


def _otel(family: Family):
    instrument = _otel_instruments.get(family.name)
    if instrument is not None:
        return instrument
    try:
        from opentelemetry import metrics as otel_metrics

        meter = otel_metrics.get_meter("ner.domain")
        if family.kind == "counter":
            instrument = meter.create_counter(family.name, description=family.description)
        elif family.kind == "histogram":
            instrument = meter.create_histogram(family.name, description=family.description)
        else:
            instrument = meter.create_up_down_counter(family.name, description=family.description)
    except Exception:
        logger.debug("otel_instrument_unavailable", extra={"family": family.name})
        return None
    _otel_instruments[family.name] = instrument
    return instrument


def _coerce(family: Family, values: dict) -> dict:
    return {label.name: label.coerce(values.get(label.name)) for label in family.labels}


def _record(family: Family, value: float, **labels) -> None:
    """Write one observation to whichever backend this process actually has.

    Never raises. A metric that can fail the work it measures is worse than no metric —
    the foundation established this rule for export and it holds here for recording too.
    """
    try:
        resolved = _coerce(family, labels)
        prom = _prom(family)
        if prom is not None:
            target = prom.labels(**resolved) if resolved else prom
            if family.kind == "counter":
                target.inc(value)
            elif family.kind == "histogram":
                target.observe(value)
            else:
                target.set(value)
        otel = _otel(family)
        if otel is not None:
            if family.kind == "histogram":
                otel.record(value, resolved)
            else:
                otel.add(value, resolved)
    except Exception:
        logger.debug("metric_record_failed", extra={"family": family.name}, exc_info=True)


def register_queue_depth_gauge(queue: str, read_depth) -> None:
    """Report a queue's depth at scrape time from `read_depth()` (design Decision 6).

    Pull-time rather than written on a timer, following the pattern the foundation
    established for `DatabasePoolCollector`: occupancy is only true at the instant it is
    read. Call this in the service that owns the queue's producer side, not in a worker.
    """
    prom = _prom(CELERY_QUEUE_DEPTH)
    if prom is None:
        return
    try:
        prom.labels(queue=CELERY_QUEUE_DEPTH.labels[0].coerce(queue)).set_function(
            lambda: _safe_depth(read_depth)
        )
    except Exception:
        logger.debug("queue_depth_gauge_unavailable", extra={"queue": queue}, exc_info=True)


def _safe_depth(read_depth) -> float:
    try:
        return float(read_depth())
    except Exception:
        # A broker that is not reachable is not a reason to fail the whole scrape.
        logger.debug("queue_depth_unavailable", exc_info=True)
        return 0.0


def error_class(exc: BaseException | str | None) -> str:
    """`type(e).__name__`, coerced into the declared set.

    Never `str(e)`: a driver message quotes the offending literal back —
    `invalid input syntax for type integer: "Priya"` — and a metric label is not redacted
    anywhere.
    """
    if exc is None:
        return NONE
    name = exc if isinstance(exc, str) else type(exc).__name__
    return name if name in ERROR_CLASSES else OTHER


# --------------------------------------------------------------------------------------
# Search-path assertion (design Decision 5)
# --------------------------------------------------------------------------------------

# The `tenant_` prefix plus identifier-safe characters only, bounded at 56 so the whole
# name stays inside Postgres's 63-character identifier limit. This is the property the
# assertion exists to enforce: it stops a value interpolated into
# `SET search_path TO {schema}` from carrying SQL structure.
#
# Deliberately *not* a UUID shape. Design Decision 5 originally specified
# `^tenant_[0-9a-f-]+$`, which no caller on this platform can satisfy — every one of the
# ~20 `_schema()` helpers renders `f"tenant_{tenant_id.replace('-', '_')}"`, so a live
# schema is `tenant_3f2a1b4c_9d8e_...`, and the fixtures seed slug-named ones
# (`tenant_test_tenant`). That pattern would fire the violation counter and an ERROR
# record on every query the platform serves, burying the one violation that mattered.
# design.md records the correction and the trade-off it accepts.
_TENANT_SCHEMA_RE = re.compile(r"^tenant_[0-9A-Za-z_-]{1,56}$")

# The logged rendering of a violating value. Bounded and character-restricted so a value
# that failed the pattern cannot itself inject structure into the log record it is
# reported in — a violation is by definition a value we did not expect.
_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_.-]")
_MAX_LOGGED_SCHEMA_CHARS = 64


def sanitize_schema_for_log(schema) -> str:
    rendered = _SANITIZE_RE.sub("?", str(schema))
    if len(rendered) > _MAX_LOGGED_SCHEMA_CHARS:
        rendered = rendered[: _MAX_LOGGED_SCHEMA_CHARS - 1] + "…"
    return rendered


def assert_tenant_schema(schema, code_path: str) -> bool:
    """Check a schema name against the tenant-schema pattern before it is interpolated.

    Returns True when the name is well-formed, False otherwise, and **never raises**.

    Raising is the right end state and the wrong step now. Nine sites build a search path
    by f-string interpolation and nothing today notices an unexpected value; converting
    one into a hard failure would choose a failure mode with no data about how often the
    condition occurs. So this counts and logs at ERROR — which the foundation's pipeline
    already delivers to Loki — and the decision to raise gets made with a non-zero or zero
    counter in hand. See design Decision 5.
    """
    if isinstance(schema, str) and _TENANT_SCHEMA_RE.match(schema):
        return True
    _record(SEARCH_PATH_VIOLATIONS, 1, code_path=code_path)
    logger.error(
        "search_path_violation",
        extra={
            "code_path": code_path,
            "schema": sanitize_schema_for_log(schema),
            "expected": "tenant_<uuid>",
        },
    )
    return False


# --------------------------------------------------------------------------------------
# Recorders — the only way a call site touches a metric
# --------------------------------------------------------------------------------------


def record_tenant_mismatch() -> None:
    _record(TENANT_MISMATCH, 1)


def record_auth_failure(reason: str) -> None:
    _record(AUTH_FAILURES, 1, reason=reason)


def record_rate_limit_rejection(tenant_id: str | None, scope: str) -> None:
    _record(RATE_LIMIT_REJECTIONS, 1, tenant_id=tenant_id, scope=scope)


def record_guardrail_decision(rule: str, decision: str) -> None:
    _record(GUARDRAIL_DECISIONS, 1, rule=rule, decision=decision)


def record_guardrail_fail_open(exc: BaseException | None = None) -> None:
    _record(GUARDRAIL_FAIL_OPEN, 1, error_class=error_class(exc))


def record_guardrail_classifier_split() -> None:
    _record(GUARDRAIL_CLASSIFIER_SPLIT, 1)


def record_entity_resolution(outcome: str, mentions_checked: int) -> None:
    _record(ENTITY_RESOLUTIONS, 1, outcome=outcome)
    _record(ENTITY_RESOLUTION_MENTIONS, float(mentions_checked), outcome=outcome)


def record_retrieval(capability: str, result_count: int) -> None:
    _record(RETRIEVAL_RESULTS, float(result_count), capability=capability)
    if result_count == 0:
        _record(RETRIEVAL_ZERO_RESULTS, 1, capability=capability)


def record_retrieval_hit_rate(capability: str, hit_rate: float) -> None:
    _record(RETRIEVAL_HIT_RATE, float(hit_rate), capability=capability)


def record_rerank_duration(seconds: float) -> None:
    _record(RERANK_DURATION, float(seconds))


def record_sql_attempt(outcome: str, defect: str | None = None) -> None:
    """One attempt. `defect` is the raw field; the payload is stripped here, once."""
    _record(SQL_ATTEMPTS, 1, outcome=outcome, defect_class=_defect_class(defect) or NONE)


def record_sql_repair_depth(repair_depth: int) -> None:
    _record(SQL_REPAIR_DEPTH, float(repair_depth))


def record_sql_generation(outcome: str, abandon_reason: str | None = None) -> None:
    _record(SQL_GENERATIONS, 1, outcome=outcome, abandon_reason=abandon_reason or NONE)


def record_sql_execution(duration_seconds: float, row_count: int, truncated: bool) -> None:
    _record(SQL_EXECUTION_DURATION, float(duration_seconds))
    _record(SQL_EXECUTION_ROWS, float(row_count))
    _record(SQL_EXECUTIONS, 1, truncated="true" if truncated else "false")


def record_llm_call(
    operation: str,
    tenant_id: str | None,
    duration_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    exc: BaseException | None = None,
) -> None:
    outcome = "error" if exc is not None else "success"
    _record(LLM_CALLS, 1, operation=operation, outcome=outcome, error_class=error_class(exc))
    _record(LLM_DURATION, float(duration_seconds), operation=operation)
    if input_tokens:
        _record(LLM_TOKENS, float(input_tokens), tenant_id=tenant_id, operation=operation, direction="input")
    if output_tokens:
        _record(LLM_TOKENS, float(output_tokens), tenant_id=tenant_id, operation=operation, direction="output")
    if cost_usd:
        _record(LLM_COST, float(cost_usd), tenant_id=tenant_id, operation=operation)


def estimate_llm_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Spend for one call at the configured rates, or 0.0 when none are configured."""
    from src.shared.config import settings

    return (
        (input_tokens / 1000.0) * settings.llm_cost_per_1k_input_usd
        + (output_tokens / 1000.0) * settings.llm_cost_per_1k_output_usd
    )


def _ambient_tenant() -> str | None:
    """The tenant on the request's context, for a call site that has no handle on one.

    Most LLM call sites are several frames below the request boundary — the guardrail
    classifier, the retrieval planner, the SQL generator — and threading a tenant argument
    through each would change signatures across three modules for a label.

    Without this fallback the tokens land under `tenant_id="unknown"`, which is worse than
    it looks: `ner_llm_tokens_total` and `ner_llm_cost_usd_total` are on the allowlist
    *because* per-tenant consumption is the one figure a trace cannot answer accurately,
    and an "unknown" bucket holding most of the volume makes the whole family useless for
    the billing question it exists to serve. Observed on the running stack: three of the
    four operations were attributing everything to `unknown`.
    """
    try:
        from src.shared.observability.context import get_tenant_id

        return get_tenant_id()
    except Exception:
        return None


@asynccontextmanager
async def measure_llm_call(operation: str, tenant_id: str | None = None):
    """Measure one provider call: latency, tokens, cost, outcome, error class.

        async with measure_llm_call("sql_generation", tenant_id) as call:
            response = await client.chat.completions.create(...)
            call.usage(response)

    Latency is measured around the provider call specifically, not around the enclosing
    stage: a slow stage that contains a fast LLM call and a slow retrieval is the exact
    ambiguity this change exists to remove.

    An exception propagates — this measures, it does not swallow — but is recorded first,
    as `type(e).__name__` mapped into the declared set. The provider's message never
    becomes a label; a rate-limit body can echo the prompt back.
    """
    call = _LLMCall(operation, tenant_id if tenant_id is not None else _ambient_tenant())
    started = time.perf_counter()
    try:
        yield call
    except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised untouched
        call._exc = exc if isinstance(exc, Exception) else None
        raise
    finally:
        call._emit(time.perf_counter() - started)


class _LLMCall:
    """Accumulator for one measured provider call."""

    __slots__ = ("operation", "tenant_id", "input_tokens", "output_tokens", "_exc", "_emitted")

    def __init__(self, operation: str, tenant_id: str | None) -> None:
        self.operation = operation
        self.tenant_id = tenant_id
        self.input_tokens = 0
        self.output_tokens = 0
        self._exc: BaseException | None = None
        self._emitted = False

    def usage(self, response) -> None:
        """Read token counts off a provider response, tolerating one that has none.

        A streamed response carries no usage block unless it was explicitly requested, so
        a call site that streams records latency and outcome and no tokens rather than
        guessing at a count.
        """
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                return
            self.input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            self.output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        except Exception:
            logger.debug("llm_usage_unreadable", extra={"operation": self.operation})

    def _emit(self, duration_seconds: float) -> None:
        if self._emitted:
            return
        self._emitted = True
        record_llm_call(
            self.operation,
            self.tenant_id,
            duration_seconds,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=estimate_llm_cost_usd(self.input_tokens, self.output_tokens),
            exc=self._exc,
        )


def record_answer(confidence: float | None, citations: int, hedged: bool) -> None:
    if confidence is not None:
        _record(ANSWER_CONFIDENCE, float(confidence))
    _record(ANSWER_CITATIONS, float(citations))
    _record(ANSWERS, 1, hedged="true" if hedged else "false")


def record_chat_request(tenant_id: str | None, outcome: str) -> None:
    _record(CHAT_REQUESTS, 1, tenant_id=tenant_id, outcome=outcome)


def record_chat_stage(stage: str, duration_seconds: float) -> None:
    _record(CHAT_STAGE_DURATION, float(duration_seconds), stage=stage)


def record_extraction_job(tenant_id: str | None, outcome: str) -> None:
    _record(EXTRACTION_JOBS, 1, tenant_id=tenant_id, outcome=outcome)


def record_extraction_stage(stage: str, duration_seconds: float) -> None:
    _record(EXTRACTION_STAGE_DURATION, float(duration_seconds), stage=stage)
    _record(EXTRACTION_STAGE_REACHED, 1, stage=stage)


def record_extraction_retry() -> None:
    _record(EXTRACTION_RETRIES, 1)


def record_extraction_partial_failure(stage: str) -> None:
    _record(EXTRACTION_PARTIAL_FAILURES, 1, stage=stage)


def record_extraction_volume(pages: int, entities: int) -> None:
    """Pages and the *aggregate* entity count. Per-type counts go on the span — see
    `EXTRACTION_ENTITIES` and design Decision 12."""
    _record(EXTRACTION_PAGES, float(pages))
    if entities:
        _record(EXTRACTION_ENTITIES, float(entities))


def record_extraction_failure(exc: BaseException | str) -> None:
    _record(EXTRACTION_FAILURES, 1, error_class=error_class(exc))


def record_projection(duration_seconds: float, source_rows: int, projected_rows: int) -> None:
    _record(PROJECTION_DURATION, float(duration_seconds))
    drift = "clean" if source_rows == projected_rows else "row_count_mismatch"
    _record(PROJECTIONS, 1, drift=drift)


def record_celery_wait(queue: str, wait_seconds: float) -> None:
    """Wait time, with a negative value clamped and counted as skew (design Decision 7)."""
    if wait_seconds < 0:
        _record(CELERY_CLOCK_SKEW, 1, queue=queue)
        wait_seconds = 0.0
    _record(CELERY_TASK_WAIT, float(wait_seconds), queue=queue)


def record_celery_duration(queue: str, duration_seconds: float) -> None:
    _record(CELERY_TASK_DURATION, float(duration_seconds), queue=queue)


def record_celery_retry(queue: str) -> None:
    _record(CELERY_TASK_RETRIES, 1, queue=queue)


def record_celery_failure(queue: str, exc: BaseException | str) -> None:
    _record(CELERY_TASK_FAILURES, 1, queue=queue, error_class=error_class(exc))


def record_celery_worker_up(queue: str, up: bool) -> None:
    _record(CELERY_WORKER_UP, 1.0 if up else 0.0, queue=queue)


def record_inference(
    path: str,
    duration_seconds: float,
    windows: int | None = None,
    batch_size: int | None = None,
    exc: BaseException | None = None,
) -> None:
    _record(INFERENCE_DURATION, float(duration_seconds), path=path)
    _record(INFERENCES, 1, path=path, outcome="error" if exc is not None else "success")
    if windows is not None:
        _record(INFERENCE_WINDOWS, float(windows))
    if batch_size is not None:
        _record(INFERENCE_BATCH_SIZE, float(batch_size))


def record_model_load(result: str, duration_seconds: float) -> None:
    _record(MODEL_LOAD_DURATION, float(duration_seconds), result=result)
    _record(MODEL_LOADS, 1, result=result)


def record_training_transition(state: str) -> None:
    _record(TRAINING_TRANSITIONS, 1, state=state)


def record_training_completion(final_state: str, duration_seconds: float, epochs: int | None = None) -> None:
    _record(TRAINING_DURATION, float(duration_seconds), final_state=final_state)
    if epochs is not None:
        _record(TRAINING_EPOCHS, float(epochs))


def record_training_failure(cause: str) -> None:
    _record(TRAINING_FAILURES, 1, cause=cause)
