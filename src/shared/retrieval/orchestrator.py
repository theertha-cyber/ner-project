import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from src.shared.config import settings
from src.shared.conversation_history import recent_messages
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.tools.base import ArgValidationError, ToolContext, ToolResult, validate_args
from src.shared.retrieval.tools.registry import ToolLookupError, ToolRegistry

logger = logging.getLogger(__name__)

SEMANTIC_CAPABILITY_NAME = "semantic_retrieval"
STRUCTURED_CAPABILITY_NAME = "structured_retrieval"

ORCHESTRATION_SYSTEM_PROMPT = (
    "You are a retrieval orchestrator for a tenant knowledge base assistant. Given the "
    "user's question and recent conversation history, decide which retrieval capabilities "
    "are needed to answer it, and call each one exactly once per distinct piece of evidence "
    "you need.\n\n"
    "Two capabilities are available.\n\n"
    "`structured_retrieval` queries the entity database — every fact an extraction model "
    "pulled out of the tenant's documents, each stored with its type (skill, employer, "
    "email, programming language, tool, degree, …), its value, and the document it came "
    "from. Use it for ANY question that names or implies a category of fact. That includes "
    "plain enumeration — 'list the tools in X's resume', 'what languages does Y know', "
    "'show every company Z worked at' — just as much as it includes counting, comparing, "
    "ranking, filtering, and aggregating. Enumerating the values of a type for one subject "
    "is its single most common use. A question that could be phrased as 'which <type> "
    "values belong to <subject>' is always a structured question.\n\n"
    "`semantic_retrieval` finds passages of document text by meaning, optionally scoped to "
    "specific documents. Use it for narrative, explanatory, or open-ended questions where "
    "the answer is prose rather than a set of facts — summaries, descriptions of what "
    "someone did, context around a fact, or anything no entity type would capture.\n\n"
    "When a question asks for a category of fact but the surrounding detail may also "
    "matter, call BOTH: the entity rows give the complete, authoritative list, and the "
    "passages give the context. Prefer calling both over guessing wrong. Any question "
    "that ENUMERATES the values of a type, or that IDENTIFIES which subjects have "
    "something ('who knows X', 'which resumes mention Y', 'list every Z'), SHALL be "
    "planned with both capabilities: the entity rows carry the authoritative set, the "
    "passages carry the wording the extractor did not capture.\n\n"
    "**Conditions that compose with AND belong in ONE invocation.** A question like "
    "'find backend engineers with AWS and Kubernetes experience' has three conditions "
    "on ONE subject, and only a single query carrying all three can find a subject that "
    "satisfies all of them. Splitting it into one invocation per condition produces "
    "three unrelated result sets whose intersection nothing downstream computes — the "
    "answer would name subjects matching any one condition as though they matched all. "
    "So: write every condition into a single `structured_retrieval` query. Call the "
    "same capability more than once ONLY when the question has genuinely separate "
    "parts — comparing two named subjects, or asking two independent questions at "
    "once — never to split the conditions of one question.\n\n"
    "**A capability sees only the arguments you give it — never this conversation.** So "
    "when the question points back at something an earlier turn established rather than "
    "naming it ('which of those candidates', 'compare the two', 'does she also know Go', "
    "'any of them', 'the ones you listed'), resolve the reference yourself from the "
    "history above and write the resolved subjects into the `query` argument in full. A "
    "query of 'which of the following candidates suit an AI engineer role' names nobody "
    "and retrieves against the whole tenant, answering a different question than the one "
    "asked; 'which of Mahalakshmi S, Hannah, or Harshith Akshayraj R.S has AI or machine "
    "learning experience' carries the referent and retrieves the right evidence. Keep "
    "every subject the user is asking about — do not silently narrow the set. If the "
    "history does not actually pin the reference down, pass the question through "
    "unresolved rather than inventing subjects.\n\n"
    "Do not attempt to answer the question yourself — only select capabilities to invoke. "
    "You will not see the results of these calls; make your best judgement about what "
    "evidence is needed up front."
)

STOP_PLAN_EXECUTED = "plan_executed"
STOP_DEADLINE = "deadline"
STOP_PLANNER_ERROR = "planner_error"
STOP_EMPTY_PLAN = "empty_plan"


@dataclass
class PlanEntry:
    capability_name: str
    arguments: dict
    rejected: bool = False
    rejection_reason: str | None = None


@dataclass
class RetrievalPlan:
    entries: list[PlanEntry] = field(default_factory=list)
    truncated: bool = False


@dataclass
class OrchestrationBudget:
    max_invocations: int
    deadline: float

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline


@dataclass
class PlanTraceEntry:
    capability_name: str
    argument_keys: list[str]
    executed: bool
    rejection_reason: str | None
    error: str | None
    result_count: int
    latency_ms: float
    degraded: bool
    # Per-capability diagnostic records (e.g. the SQL recovery loop's per-attempt
    # trace). Reaches ChatState["plan_trace"] via the existing asdict() conversion in
    # retrieval_execution_node; internal state only, absent from every HTTP schema.
    diagnostics: list = field(default_factory=list)


# Closed set of per-invocation outcomes. The distinction that matters most is
# `empty` vs `failed`: the old collapsed booleans could express neither separately nor
# partially, so a failed source and a source that legitimately found nothing produced
# the same downstream behaviour — an answer asserting the data does not exist.
OUTCOME_NOT_ATTEMPTED = "not_attempted"
OUTCOME_OK = "ok"
OUTCOME_EMPTY = "empty"
OUTCOME_FAILED = "failed"
OUTCOME_SKIPPED = "skipped"

ATTEMPTED_OUTCOMES = frozenset({OUTCOME_OK, OUTCOME_EMPTY, OUTCOME_FAILED})


@dataclass
class CapabilityStatus:
    """What one plan entry actually did. `error` holds the specific failure text, never
    a generic summary — the summary is what made the old signal useless for diagnosis."""

    capability_name: str
    outcome: str
    error: str | None = None
    result_count: int = 0
    # Why an entry was `not_attempted` or `skipped`. Never populated for an attempt.
    reason: str | None = None
    # Per-attempt diagnostics the capability produced (e.g. the SQL recovery loop's
    # per-attempt trace), carried so a failure can be explained without the plan trace.
    diagnostics: list = field(default_factory=list)
    # True for the bounded structured-to-semantic recovery invocation, so a recovery
    # outcome is never mistaken for something the planner asked for.
    recovery: bool = False

    def as_dict(self) -> dict:
        return {
            "capability_name": self.capability_name,
            "outcome": self.outcome,
            "error": self.error,
            "result_count": self.result_count,
            "reason": self.reason,
            "recovery": self.recovery,
        }


@dataclass
class RetrievalStatus:
    """The turn's retrieval outcome, as one value with named consumers.

    Replaces `retrieval_error` / `sql_error`, which were written on every turn and read
    on none: they could not express partial failure (they fired only when *every*
    invocation of a kind failed) and replaced the specific error with a fixed string."""

    entries: list[CapabilityStatus] = field(default_factory=list)
    planning_degraded: bool = False
    stop_reason: str | None = None

    def attempted(self) -> list[CapabilityStatus]:
        return [e for e in self.entries if e.outcome in ATTEMPTED_OUTCOMES]

    def failures(self) -> list[CapabilityStatus]:
        return [e for e in self.entries if e.outcome == OUTCOME_FAILED]

    def skips(self) -> list[CapabilityStatus]:
        return [e for e in self.entries if e.outcome == OUTCOME_SKIPPED]

    def has_failure(self) -> bool:
        return bool(self.failures())

    def has_failure_or_skip(self) -> bool:
        return bool(self.failures() or self.skips())

    def failed_capability_names(self) -> list[str]:
        return sorted({e.capability_name for e in self.failures()})

    def entries_for(self, capability_name: str) -> list[CapabilityStatus]:
        return [e for e in self.entries if e.capability_name == capability_name]

    def outcome_for(self, capability_name: str) -> str | None:
        """The strongest signal any invocation of this capability produced, ordered
        failed > ok > empty > skipped > not_attempted, so a partial failure is never
        reported as a clean run."""
        outcomes = {e.outcome for e in self.entries_for(capability_name)}
        for candidate in (OUTCOME_FAILED, OUTCOME_OK, OUTCOME_EMPTY, OUTCOME_SKIPPED, OUTCOME_NOT_ATTEMPTED):
            if candidate in outcomes:
                return candidate
        return None

    def as_dict(self) -> dict:
        return {
            "entries": [e.as_dict() for e in self.entries],
            "planning_degraded": self.planning_degraded,
            "stop_reason": self.stop_reason,
        }


@dataclass
class OrchestrationResult:
    chunks: list[RetrievalResult]
    sql_results: list[dict]
    status: RetrievalStatus
    plan_trace: list[PlanTraceEntry]
    plan_truncated: bool
    # `{"returned": int, "matched": int | None, "truncated": bool}` across every
    # structured invocation, or None when none reported it.
    sql_completeness: dict | None = None

    # Views onto `status`, not a second channel: there is one stored value and these
    # read and write it. Kept because callers and the eval runner speak in these terms.
    @property
    def orchestration_degraded(self) -> bool:
        return self.status.planning_degraded

    @orchestration_degraded.setter
    def orchestration_degraded(self, value: bool) -> None:
        self.status.planning_degraded = value

    @property
    def orchestration_stop_reason(self) -> str | None:
        return self.status.stop_reason

    @orchestration_stop_reason.setter
    def orchestration_stop_reason(self, value: str | None) -> None:
        self.status.stop_reason = value


def _resolve_entry(entry: PlanEntry, registry: ToolRegistry):
    """Returns (tool_or_None, invalid_reason_or_None). Marks the entry rejected in place."""
    try:
        tool = registry.get(entry.capability_name)
    except ToolLookupError:
        entry.rejected = True
        entry.rejection_reason = f"no capability registered with name '{entry.capability_name}'"
        return None, entry.rejection_reason

    try:
        validate_args(tool.args_schema, entry.arguments)
    except ArgValidationError as e:
        entry.rejected = True
        entry.rejection_reason = str(e)
        return None, entry.rejection_reason

    return tool, None


def _build_messages(message: str, conversation_context: list[dict] | None) -> list[dict]:
    messages = [{"role": "system", "content": ORCHESTRATION_SYSTEM_PROMPT}]
    for turn in recent_messages(conversation_context):
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})
    return messages


async def plan_retrieval(
    message: str,
    conversation_context: list[dict] | None,
    llm_client,
    llm_model: str,
    registry: ToolRegistry,
) -> RetrievalPlan:
    """Makes exactly one planning LLM call and returns the resulting plan. Entries are
    validated against their capability's `args_schema` here; invalid entries are marked
    rejected but kept in the plan so the caller can trace them. Raises whatever the LLM
    client raises — the caller is responsible for the degraded fallback."""
    messages = _build_messages(message, conversation_context)
    response = await llm_client.chat.completions.create(
        model=llm_model, messages=messages, tools=registry.export_schemas(), tool_choice="auto", temperature=0,
    )

    assistant_message = response.choices[0].message
    tool_calls = getattr(assistant_message, "tool_calls", None) or []

    entries: list[PlanEntry] = []
    for call in tool_calls:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            entry = PlanEntry(capability_name=call.function.name, arguments={})
            entry.rejected = True
            entry.rejection_reason = "arguments are not valid JSON"
            entries.append(entry)
            continue
        entries.append(PlanEntry(capability_name=call.function.name, arguments=arguments))

    for entry in entries:
        if entry.rejected:
            continue
        _resolve_entry(entry, registry)

    return RetrievalPlan(entries=entries)


async def _invoke_entry(entry: PlanEntry, registry: ToolRegistry, context: ToolContext) -> tuple[ToolResult | None, PlanTraceEntry]:
    if entry.rejected:
        trace = PlanTraceEntry(
            capability_name=entry.capability_name, argument_keys=sorted(entry.arguments.keys()) if entry.arguments else [],
            executed=False, rejection_reason=entry.rejection_reason, error=None,
            result_count=0, latency_ms=0.0, degraded=False,
        )
        return None, trace

    tool = registry.get(entry.capability_name)
    result = await tool.call(entry.arguments, context)
    trace = PlanTraceEntry(
        capability_name=entry.capability_name, argument_keys=sorted(entry.arguments.keys()) if entry.arguments else [],
        executed=True, rejection_reason=None, error=result.error, result_count=len(result.results),
        latency_ms=result.latency_ms, degraded=result.degraded, diagnostics=list(result.diagnostics),
    )
    return result, trace


def _entry_status(
    entry: PlanEntry, result: ToolResult | None, recovery: bool = False
) -> CapabilityStatus:
    """Classifies one dispatched (or undispatched) entry. Note the order: an error is
    a failure whatever the result count, and zero rows without an error is `empty`,
    never `failed` — that distinction is the whole point of the value."""
    if result is None:
        return CapabilityStatus(
            capability_name=entry.capability_name,
            outcome=OUTCOME_NOT_ATTEMPTED,
            reason=entry.rejection_reason,
            recovery=recovery,
        )
    if result.error:
        return CapabilityStatus(
            capability_name=entry.capability_name,
            outcome=OUTCOME_FAILED,
            error=result.error,
            diagnostics=list(result.diagnostics),
            recovery=recovery,
        )
    count = len(result.results)
    return CapabilityStatus(
        capability_name=entry.capability_name,
        outcome=OUTCOME_OK if count else OUTCOME_EMPTY,
        result_count=count,
        diagnostics=list(result.diagnostics),
        recovery=recovery,
    )


def _rank_normalised(results: list, basis: str) -> list[RetrievalResult]:
    """Stamps each result of one invocation with a rank-derived score in (0, 1].

    Two invocations of the same capability can be scored on incomparable scales — the
    reranker falls back to unranked fusion candidates on failure, so one may carry
    cross-encoder logits (possibly negative) and the other RRF scores around 0.016.
    Sorting those against each other is arbitrary. Rank position is what they share.

    The raw score is preserved on the result, with the basis that produced it."""
    items = [r for r in results if isinstance(r, RetrievalResult)]
    total = len(items)
    normalised: list[RetrievalResult] = []
    for rank, item in enumerate(items):
        normalised.append(item.model_copy(update={
            "merge_rank_score": (total - rank) / total,
            "score_basis": item.score_basis or basis,
        }))
    return normalised


def _merge_completeness(existing: dict | None, incoming: dict | None) -> dict | None:
    """Combines completeness across structured invocations. `matched` is unknown for the
    whole turn as soon as it is unknown for any part of it — reporting a partial total
    as if it were the whole is the failure mode this reporting exists to prevent."""
    if not incoming:
        return existing
    if not existing:
        return dict(incoming)

    matched = None
    if existing.get("matched") is not None and incoming.get("matched") is not None:
        matched = existing["matched"] + incoming["matched"]
    return {
        "returned": existing.get("returned", 0) + incoming.get("returned", 0),
        "matched": matched,
        "truncated": bool(existing.get("truncated")) or bool(incoming.get("truncated")),
    }


def _accumulate(
    entries_and_results: list[tuple[PlanEntry, ToolResult | None]]
) -> tuple[list[RetrievalResult], list[dict], list[CapabilityStatus], dict | None]:
    """Merges evidence and classifies every entry. One status per entry, in plan order.

    Nothing here collapses several entries into one signal: a plan whose first
    structured invocation failed and whose second returned rows reports both, and the
    rows from the second are still accumulated."""
    chunks_by_key: dict[tuple[str, int], RetrievalResult] = {}
    sql_results: list[dict] = []
    statuses: list[CapabilityStatus] = []
    completeness: dict | None = None

    for entry, result in entries_and_results:
        statuses.append(_entry_status(entry, result))
        if result is None or result.error:
            continue
        if entry.capability_name == SEMANTIC_CAPABILITY_NAME:
            basis = "fusion" if result.degraded else "reranker"
            for item in _rank_normalised(result.results, basis):
                key = (item.document_id, item.chunk_index)
                existing = chunks_by_key.get(key)
                if existing is None or item.merge_rank_score > existing.merge_rank_score:
                    chunks_by_key[key] = item
        elif entry.capability_name == STRUCTURED_CAPABILITY_NAME:
            sql_results.extend(result.results)
            completeness = _merge_completeness(completeness, result.result_completeness)

    # Ordered on the normalised basis, with the raw score untouched for display. A
    # single invocation's normalised scores are strictly decreasing in its own order,
    # so its relative ordering is unchanged by construction.
    chunks = sorted(chunks_by_key.values(), key=lambda c: c.merge_rank_score or 0.0, reverse=True)
    return chunks[: settings.retrieval_merge_max_chunks], sql_results, statuses, completeness


RECOVERY_SKIP_BUDGET = "insufficient remaining budget for semantic recovery"
RECOVERY_SKIP_INVOCATION_CAP = "invocation cap reached before semantic recovery"


def _recovery_is_warranted(entries: list[PlanEntry], statuses: list[CapabilityStatus]) -> bool:
    """Whether a structured-only plan that found nothing gets one semantic attempt.

    The observed case: a structurally correct statement returns zero rows only because
    the anchor entity is missing from the extraction, while the answer is sitting in the
    document text the plan never asked for. One unconditional fallback recovers that
    class. It fires for `failed` as well as `empty` — a structured source that broke
    leaves the turn with nothing either way."""
    if any(e.capability_name == SEMANTIC_CAPABILITY_NAME for e in entries):
        return False

    structured = [s for s in statuses if s.capability_name == STRUCTURED_CAPABILITY_NAME]
    if not structured:
        return False
    return all(s.outcome in (OUTCOME_EMPTY, OUTCOME_FAILED) for s in structured)


async def execute_plan(
    plan: RetrievalPlan,
    registry: ToolRegistry,
    context_factory,
    budget: OrchestrationBudget,
    recovery_query: str | None = None,
) -> OrchestrationResult:
    """Executes every valid entry in `plan` concurrently, each against its own
    `ToolContext` produced by `context_factory()` — an async context manager
    (`async with context_factory() as context: ...`) that yields a `ToolContext` backed
    by a fresh `AsyncSession` and closes it on exit. Every invocation must get its own
    session, since a single AsyncSession cannot serve concurrent statements. Entries
    beyond `budget.max_invocations` are discarded before execution; discarded entries are
    still traced. Rejected entries (from `plan_retrieval`) are never executed and never
    open a context."""
    entries = list(plan.entries)
    truncated = plan.truncated
    executable_indices = [i for i, e in enumerate(entries) if not e.rejected]

    if len(executable_indices) > budget.max_invocations:
        for i in executable_indices[budget.max_invocations:]:
            entries[i].rejected = True
            entries[i].rejection_reason = "discarded: plan invocation cap exceeded"
        truncated = True
        executable_indices = executable_indices[: budget.max_invocations]

    stop_reason = STOP_PLAN_EXECUTED
    if budget.expired():
        stop_reason = STOP_DEADLINE
        for i in executable_indices:
            entries[i].rejected = True
            entries[i].rejection_reason = "discarded: deadline exhausted before dispatch"
        executable_indices = []

    async def _run_one(idx: int):
        if entries[idx].rejected:
            return idx, await _invoke_entry(entries[idx], registry, None)
        async with context_factory() as context:
            return idx, await _invoke_entry(entries[idx], registry, context)

    use_candidate_filtering = (
        settings.candidate_document_filtering_enabled
        and any(entries[i].capability_name == STRUCTURED_CAPABILITY_NAME for i in executable_indices)
        and any(entries[i].capability_name == SEMANTIC_CAPABILITY_NAME for i in executable_indices)
    )

    if use_candidate_filtering:
        structured_indices = [i for i in executable_indices if entries[i].capability_name == STRUCTURED_CAPABILITY_NAME]
        other_executable_indices = [i for i in executable_indices if i not in structured_indices]
        rejected_indices = [i for i in range(len(entries)) if entries[i].rejected]

        structured_dispatched = list(await asyncio.gather(*(_run_one(i) for i in structured_indices))) if structured_indices else []

        candidate_ids: set[str] = set()
        for _idx, (result, _trace) in structured_dispatched:
            if result is not None and not result.error:
                candidate_ids |= result.candidate_document_ids

        if candidate_ids:
            for i in other_executable_indices:
                entry = entries[i]
                if entry.capability_name == SEMANTIC_CAPABILITY_NAME and "scope" not in entry.arguments:
                    entry.arguments = {
                        **entry.arguments,
                        "scope": {"type": "document", "document_ids": sorted(candidate_ids)},
                    }

        remaining_indices = other_executable_indices + rejected_indices
        remaining_dispatched = list(await asyncio.gather(*(_run_one(i) for i in remaining_indices))) if remaining_indices else []
        dispatched = structured_dispatched + remaining_dispatched
    else:
        dispatched = await asyncio.gather(*(_run_one(i) for i in range(len(entries))))

    trace: list[PlanTraceEntry] = [None] * len(entries)  # type: ignore[list-item]
    results_by_index: dict[int, ToolResult | None] = {}
    for idx, (result, entry_trace) in dispatched:
        trace[idx] = entry_trace
        results_by_index[idx] = result

    # Plan order, not dispatch order: a status list a caller can line up against the
    # plan is worth more than one ordered by whichever invocation happened to finish
    # first.
    entries_and_results = [(entries[i], results_by_index.get(i)) for i in range(len(entries))]

    chunks, sql_results, statuses, completeness = _accumulate(entries_and_results)

    # One fixed recovery invocation. Not a loop, not a re-plan, not an observe/act
    # cycle: exactly one `semantic_retrieval` call on the turn's original question,
    # made at most once, and only when the plan asked for no semantic evidence at all
    # and the structured evidence it did ask for came back with nothing.
    if recovery_query and _recovery_is_warranted(entries, statuses):
        recovery_entry = PlanEntry(
            capability_name=SEMANTIC_CAPABILITY_NAME, arguments={"query": recovery_query},
        )
        used_invocations = sum(1 for s in statuses if s.outcome in ATTEMPTED_OUTCOMES)
        remaining_seconds = budget.deadline - time.monotonic()

        if used_invocations >= budget.max_invocations:
            statuses.append(CapabilityStatus(
                capability_name=SEMANTIC_CAPABILITY_NAME, outcome=OUTCOME_SKIPPED,
                reason=RECOVERY_SKIP_INVOCATION_CAP, recovery=True,
            ))
        elif remaining_seconds < settings.retrieval_recovery_min_budget_seconds:
            # Recorded as skipped, never as an empty result: "we did not look" and
            # "we looked and found nothing" must not reach the answer model as one thing.
            statuses.append(CapabilityStatus(
                capability_name=SEMANTIC_CAPABILITY_NAME, outcome=OUTCOME_SKIPPED,
                reason=RECOVERY_SKIP_BUDGET, recovery=True,
            ))
        else:
            _resolve_entry(recovery_entry, registry)
            async with context_factory() as recovery_context:
                recovery_result, recovery_trace = await _invoke_entry(
                    recovery_entry, registry, recovery_context,
                )
            entries.append(recovery_entry)
            trace.append(recovery_trace)
            recovery_status = _entry_status(recovery_entry, recovery_result, recovery=True)
            statuses.append(recovery_status)

            if recovery_result is not None and not recovery_result.error:
                recovered_chunks, _, _, _ = _accumulate([(recovery_entry, recovery_result)])
                chunks = recovered_chunks
            logger.info(
                "orchestrator: structured-only plan returned nothing, semantic recovery "
                "outcome=%s chunks=%d", recovery_status.outcome, len(chunks),
            )

    status = RetrievalStatus(entries=statuses, planning_degraded=False, stop_reason=stop_reason)

    return OrchestrationResult(
        chunks=chunks, sql_results=sql_results, status=status,
        plan_trace=trace, plan_truncated=truncated, sql_completeness=completeness,
    )


async def orchestrate_retrieval(
    message: str,
    conversation_context: list[dict] | None,
    llm_client,
    llm_model: str,
    registry: ToolRegistry,
    context_factory,
    budget: OrchestrationBudget,
) -> OrchestrationResult:
    """Top-level entry point: plans, executes, and degrades to a fallback plan (both
    capabilities on the raw query) if planning raised or every entry was rejected."""
    try:
        plan = await plan_retrieval(message, conversation_context, llm_client, llm_model, registry)
    except Exception as e:
        logger.warning("orchestrator: planning call failed, falling back to raw-query plan: %s", e)
        return await _degraded_fallback(message, registry, context_factory, budget, STOP_PLANNER_ERROR)

    if not plan.entries or all(e.rejected for e in plan.entries):
        logger.info("orchestrator: planner produced no usable entries, falling back to raw-query plan")
        return await _degraded_fallback(message, registry, context_factory, budget, STOP_EMPTY_PLAN)

    return await execute_plan(plan, registry, context_factory, budget, recovery_query=message)


def build_fallback_plan(message: str, registry: ToolRegistry) -> RetrievalPlan:
    """The degraded fallback plan: both capabilities invoked on the raw user query.
    Used when planning fails or produces no usable entries. Exposed publicly so
    callers that split planning and execution across two steps (e.g. separate graph
    nodes, for plan visibility in state) can build the same fallback plan without
    duplicating capability names or argument shape."""
    fallback_plan = RetrievalPlan(entries=[
        PlanEntry(capability_name=SEMANTIC_CAPABILITY_NAME, arguments={"query": message}),
        PlanEntry(capability_name=STRUCTURED_CAPABILITY_NAME, arguments={"query": message}),
    ])
    for entry in fallback_plan.entries:
        _resolve_entry(entry, registry)
    return fallback_plan


async def _degraded_fallback(
    message: str,
    registry: ToolRegistry,
    context_factory,
    budget: OrchestrationBudget,
    stop_reason: str,
) -> OrchestrationResult:
    fallback_plan = build_fallback_plan(message, registry)
    result = await execute_plan(fallback_plan, registry, context_factory, budget)
    result.orchestration_degraded = True
    result.orchestration_stop_reason = stop_reason
    logger.info(
        "graph node=orchestrator degraded=True stop_reason=%s", stop_reason,
    )
    return result
