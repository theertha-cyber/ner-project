import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from src.shared.config import settings
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
    "you need. Two capabilities are available: `semantic_retrieval` finds relevant document "
    "content by meaning, optionally scoped to specific documents; `structured_retrieval` "
    "answers questions against extracted structured entity data (counts, aggregates, "
    "lookups). Call both if the question needs both. Call the same capability more than "
    "once if the question has multiple distinct parts requiring separate lookups (e.g. "
    "comparing two documents). Do not attempt to answer the question yourself — only "
    "select capabilities to invoke. You will not see the results of these calls; make your "
    "best judgement about what evidence is needed up front."
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


@dataclass
class OrchestrationResult:
    chunks: list[RetrievalResult]
    sql_results: list[dict]
    retrieval_error: str | None
    sql_error: str | None
    plan_trace: list[PlanTraceEntry]
    plan_truncated: bool
    orchestration_degraded: bool
    orchestration_stop_reason: str


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
    if conversation_context:
        for turn in conversation_context[-3:]:
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
        latency_ms=result.latency_ms, degraded=result.degraded,
    )
    return result, trace


def _accumulate(entries_and_results: list[tuple[PlanEntry, ToolResult | None]]) -> tuple[list[RetrievalResult], list[dict], str | None, str | None]:
    chunks_by_key: dict[tuple[str, int], RetrievalResult] = {}
    sql_results: list[dict] = []
    semantic_call_count = 0
    semantic_error_count = 0
    structured_call_count = 0
    structured_error_count = 0

    for entry, result in entries_and_results:
        if result is None:
            continue
        if entry.capability_name == SEMANTIC_CAPABILITY_NAME:
            semantic_call_count += 1
            if result.error:
                semantic_error_count += 1
                continue
            for item in result.results:
                if not isinstance(item, RetrievalResult):
                    continue
                key = (item.document_id, item.chunk_index)
                existing = chunks_by_key.get(key)
                if existing is None or item.similarity_score > existing.similarity_score:
                    chunks_by_key[key] = item
        elif entry.capability_name == STRUCTURED_CAPABILITY_NAME:
            structured_call_count += 1
            if result.error:
                structured_error_count += 1
                continue
            sql_results.extend(result.results)

    chunks = sorted(chunks_by_key.values(), key=lambda c: c.similarity_score, reverse=True)
    retrieval_error = "all semantic_retrieval invocations failed" if (
        semantic_call_count > 0 and semantic_error_count == semantic_call_count
    ) else None
    sql_error = "all structured_retrieval invocations failed" if (
        structured_call_count > 0 and structured_error_count == structured_call_count
    ) else None

    return chunks, sql_results, retrieval_error, sql_error


async def execute_plan(
    plan: RetrievalPlan,
    registry: ToolRegistry,
    context_factory,
    budget: OrchestrationBudget,
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

    entries_and_results: list[tuple[PlanEntry, ToolResult | None]] = []
    trace: list[PlanTraceEntry] = [None] * len(entries)  # type: ignore[list-item]
    for idx, (result, entry_trace) in dispatched:
        trace[idx] = entry_trace
        entries_and_results.append((entries[idx], result))

    chunks, sql_results, retrieval_error, sql_error = _accumulate(entries_and_results)

    return OrchestrationResult(
        chunks=chunks, sql_results=sql_results, retrieval_error=retrieval_error, sql_error=sql_error,
        plan_trace=trace, plan_truncated=truncated, orchestration_degraded=False, orchestration_stop_reason=stop_reason,
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

    return await execute_plan(plan, registry, context_factory, budget)


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
