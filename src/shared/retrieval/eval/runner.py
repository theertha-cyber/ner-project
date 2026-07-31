import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from src.shared.retrieval.config import RetrievalConfig
from src.shared.retrieval.eval.golden_set import GoldenQuery
from src.shared.retrieval.eval.metrics import AggregateMetrics, Judgment, QueryMetrics, RankedItem, aggregate, compute_query_metrics
from src.shared.retrieval.orchestrator import OrchestrationBudget, orchestrate_retrieval
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.registry import ToolRegistry


@dataclass(frozen=True)
class MatrixConfiguration:
    name: str
    retrieval_config: RetrievalConfig
    is_orchestrated: bool = False
    planner_client_factory: Callable[[], object] | None = None
    llm_model: str = "eval-planner"
    max_invocations: int = 3
    deadline_seconds: float = 8.0


@dataclass
class QueryRunResult:
    query_id: str
    metrics: QueryMetrics
    degraded: bool
    error: str | None


@dataclass
class ConfigurationResult:
    name: str
    retrieval_config: RetrievalConfig
    per_query: list[QueryRunResult] = field(default_factory=list)
    aggregate: AggregateMetrics | None = None
    degraded_query_count: int = 0


@dataclass
class MatrixResult:
    configurations: list[ConfigurationResult] = field(default_factory=list)


ContextFactory = Callable[[MatrixConfiguration, GoldenQuery], ToolContext | Awaitable[ToolContext]]


async def _resolve_context(context_factory: ContextFactory, config: MatrixConfiguration, query: GoldenQuery) -> ToolContext:
    result = context_factory(config, query)
    if hasattr(result, "__await__"):
        return await result
    return result


async def run_query(
    query: GoldenQuery,
    registry: ToolRegistry,
    context: ToolContext,
    k: int,
) -> QueryRunResult:
    tool = registry.get("semantic_retrieval")
    tool_result = await tool.call({"query": query.query, "top_k": k}, context)

    if tool_result.error is not None:
        metrics = QueryMetrics(
            query_id=query.query_id, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0,
            skipped=True, skip_reason=f"tool error: {tool_result.error}",
        )
        return QueryRunResult(query_id=query.query_id, metrics=metrics, degraded=tool_result.degraded, error=tool_result.error)

    ranked = [RankedItem(document_id=r.document_id, chunk_index=r.chunk_index) for r in tool_result.results]
    judgments = [Judgment(document_id=j.document_id, chunk_index=j.chunk_index, grade=j.grade) for j in query.relevant]
    metrics = compute_query_metrics(query.query_id, ranked, judgments, k)
    return QueryRunResult(query_id=query.query_id, metrics=metrics, degraded=tool_result.degraded, error=None)


async def run_query_orchestrated(
    query: GoldenQuery,
    registry: ToolRegistry,
    context: ToolContext,
    k: int,
    config: MatrixConfiguration,
) -> QueryRunResult:
    """Runs a golden-set query through the Intent Orchestrator's plan-and-execute
    path (redesign-retrieval-orchestration), rather than the retired bounded agentic
    loop, so eval results are directly comparable to the direct-capability baseline
    configurations run through `run_query`."""

    @asynccontextmanager
    async def context_factory():
        yield context

    try:
        llm_client = config.planner_client_factory()
        budget = OrchestrationBudget(
            max_invocations=config.max_invocations, deadline=time.monotonic() + config.deadline_seconds,
        )
        result = await orchestrate_retrieval(
            query.query, None, llm_client, config.llm_model, registry, context_factory, budget,
        )
    except Exception as e:
        metrics = QueryMetrics(
            query_id=query.query_id, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0,
            skipped=True, skip_reason=f"orchestrator error: {e}",
        )
        return QueryRunResult(query_id=query.query_id, metrics=metrics, degraded=True, error=str(e))

    if not result.chunks and (result.retrieval_error is not None or result.orchestration_degraded):
        failure = result.retrieval_error or result.orchestration_stop_reason
        metrics = QueryMetrics(
            query_id=query.query_id, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0,
            skipped=True, skip_reason=f"orchestrator failure: {failure}",
        )
        return QueryRunResult(query_id=query.query_id, metrics=metrics, degraded=result.orchestration_degraded, error=failure)

    ranked = [RankedItem(document_id=c.document_id, chunk_index=c.chunk_index) for c in result.chunks]
    judgments = [Judgment(document_id=j.document_id, chunk_index=j.chunk_index, grade=j.grade) for j in query.relevant]
    metrics = compute_query_metrics(query.query_id, ranked, judgments, k)
    return QueryRunResult(query_id=query.query_id, metrics=metrics, degraded=result.orchestration_degraded, error=None)


async def run_configuration(
    golden_queries: list[GoldenQuery],
    config: MatrixConfiguration,
    context_factory: ContextFactory,
    registry_factory: Callable[[], ToolRegistry] = build_default_registry,
    k: int = 5,
) -> ConfigurationResult:
    registry = registry_factory()
    per_query: list[QueryRunResult] = []
    for query in golden_queries:
        context = await _resolve_context(context_factory, config, query)
        if config.is_orchestrated:
            per_query.append(await run_query_orchestrated(query, registry, context, k, config))
        else:
            per_query.append(await run_query(query, registry, context, k))

    query_metrics = [r.metrics for r in per_query]
    agg = aggregate(query_metrics)
    # A query that errored is already recorded as skipped in `metrics`; it is not
    # double-excluded here — `aggregate` already excludes every skipped entry.
    degraded_count = sum(1 for r in per_query if r.degraded)
    return ConfigurationResult(name=config.name, retrieval_config=config.retrieval_config, per_query=per_query, aggregate=agg, degraded_query_count=degraded_count)


async def run_matrix(
    golden_queries: list[GoldenQuery],
    configurations: list[MatrixConfiguration],
    context_factory: ContextFactory,
    registry_factory: Callable[[], ToolRegistry] = build_default_registry,
    k: int = 5,
) -> MatrixResult:
    results = []
    for config in configurations:
        results.append(await run_configuration(golden_queries, config, context_factory, registry_factory, k))
    return MatrixResult(configurations=results)
