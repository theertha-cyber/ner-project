import json as _json
from types import SimpleNamespace

import pytest

from src.shared.config import settings
from src.shared.retrieval.config import RetrievalConfig
from src.shared.retrieval.eval.embeddings import PrecomputedEmbeddingService
from src.shared.retrieval.eval.golden_set import GoldenQuery, Judgment
from src.shared.retrieval.eval.report import build_json_report, build_markdown_summary
from src.shared.retrieval.eval.metrics import SCORING_RULE
from src.shared.retrieval.eval.runner import MatrixConfiguration, MatrixResult, run_configuration, run_matrix
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever
from src.shared.retrieval.tools.base import ToolContext, ToolResult
from src.shared.retrieval.tools.registry import ToolRegistry

pytestmark = [pytest.mark.asyncio]


def _queries(n: int) -> list[GoldenQuery]:
    return [
        GoldenQuery(query_id=f"q{i}", query=f"query {i}", relevant=[Judgment(document_id="doc-a", chunk_index=0, grade=2)])
        for i in range(n)
    ]


class SpyTool:
    name = "semantic_retrieval"

    def __init__(self, result_fn):
        self.calls: list[dict] = []
        self.result_fn = result_fn

    async def call(self, args, context):
        self.calls.append(args)
        return self.result_fn(args, context)


class SpyRegistry:
    def __init__(self, tool: SpyTool):
        self._tool = tool

    def get(self, name: str):
        assert name == "semantic_retrieval"
        return self._tool


def _healthy_result(args, context):
    return ToolResult(tool_name="semantic_retrieval", results=[
        RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
    ])


class TestRunnerInvokesToolLayer:
    """Covers verification.md row 56."""

    async def test_runner_invokes_capability_per_query(self):
        tool = SpyTool(_healthy_result)
        registry = SpyRegistry(tool)
        queries = _queries(5)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(queries, config, context_factory, registry_factory=lambda: registry, k=5)

        assert len(tool.calls) == 5
        assert len(result.per_query) == 5


class TestToolErrorNotFatal:
    """Covers verification.md row 57."""

    async def test_tool_error_recorded_not_fatal(self):
        def result_fn(args, context):
            if args["query"] == "query 2":
                return ToolResult(tool_name="semantic_retrieval", results=[], error="boom")
            return _healthy_result(args, context)

        tool = SpyTool(result_fn)
        registry = SpyRegistry(tool)
        queries = _queries(5)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(queries, config, context_factory, registry_factory=lambda: registry, k=5)

        assert len(result.per_query) == 5
        failed = [r for r in result.per_query if r.error]
        assert len(failed) == 1
        assert failed[0].query_id == "q2"
        # The failed query scores zero and stays in the denominator — it used to be
        # marked skipped and excluded, which is why a broken configuration could score
        # as well as a working one.
        assert result.aggregate.query_count == 5
        assert result.aggregate.failed_count == 1


class TestDegradedAndFailedQueriesScoreZero:
    """verification.md rows 81, 82, 83. Under the old rule a query whose run degraded or
    errored was marked skipped and excluded from the mean, so the regression gate could
    not fail on a configuration that broke on half the golden set."""

    async def test_orchestrator_failure_scores_zero_and_counts(self):
        def result_fn(args, context):
            if args["query"] in ("query 0", "query 1"):
                return ToolResult(tool_name="semantic_retrieval", results=[], error="boom")
            return _healthy_result(args, context)

        queries = _queries(4)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(
            queries, config, context_factory,
            registry_factory=lambda: SpyRegistry(SpyTool(result_fn)), k=5,
        )

        failed = [r for r in result.per_query if r.metrics.failed]
        assert len(failed) == 2
        for run in failed:
            assert run.metrics.recall_at_k == 0.0
            assert run.metrics.ndcg_at_k == 0.0
            assert run.metrics.skipped is False

        assert result.aggregate.query_count == 4
        # Two of four scored zero, so the mean is halved rather than unaffected.
        assert result.aggregate.ndcg_at_k == pytest.approx(0.5)

    async def test_degraded_planning_scores_zero(self):
        def orchestrated_result_fn(args, context):
            return ToolResult(tool_name="semantic_retrieval", results=[])

        def orchestrated_registry_factory():
            reg = ToolRegistry()
            reg.register(ScriptedSemanticRetrievalTool(orchestrated_result_fn))
            return reg

        queries = _queries(2)
        config = MatrixConfiguration(
            name="orchestrated", retrieval_config=RetrievalConfig(), is_orchestrated=True,
            planner_client_factory=lambda: ScriptedEvalPlanner(fail_query_ids={"query 1"}),
        )

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(
            queries, config, context_factory, registry_factory=orchestrated_registry_factory, k=5,
        )

        degraded = [r for r in result.per_query if r.degraded]
        assert len(degraded) == 1
        assert degraded[0].metrics.skipped is False
        assert degraded[0].metrics.ndcg_at_k == 0.0
        assert result.aggregate.query_count == 2
        assert result.aggregate.degraded_count == 1

    async def test_aggregate_reports_failure_counts(self):
        def result_fn(args, context):
            if args["query"] == "query 0":
                return ToolResult(tool_name="semantic_retrieval", results=[], error="boom")
            return _healthy_result(args, context)

        queries = _queries(3)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(
            queries, config, context_factory,
            registry_factory=lambda: SpyRegistry(SpyTool(result_fn)), k=5,
        )

        assert result.aggregate.failed_count == 1
        assert result.aggregate.query_count == 3
        assert result.failed_query_count == 1
        assert result.aggregate.scoring_rule == SCORING_RULE


class TestMatrixPerConfigAggregates:
    async def test_matrix_produces_per_config_aggregates(self):
        tool = SpyTool(_healthy_result)
        registry = SpyRegistry(tool)
        queries = _queries(3)
        configs = [
            MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig(top_k=3)),
            MatrixConfiguration(name="hybrid", retrieval_config=RetrievalConfig(top_k=5)),
        ]

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        matrix = await run_matrix(queries, configs, context_factory, registry_factory=lambda: registry, k=5)

        assert len(matrix.configurations) == 2
        names = {c.name for c in matrix.configurations}
        assert names == {"dense", "hybrid"}
        for c in matrix.configurations:
            assert c.aggregate is not None


class TestConfigDoesNotLeakToGlobalSettings:
    async def test_config_does_not_leak_and_reranking_applies(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", True)
        before = settings.reranker_enabled

        class WrappedSpy:
            def __init__(self):
                self.calls = 0

            async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
                return [RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)]

        class SpyReranker:
            def __init__(self):
                self.calls = 0

            async def rerank(self, query, results, top_k=None, jwt_token=None):
                self.calls += 1
                return results

        reranker = SpyReranker()

        def context_factory(cfg, query):
            retriever = RerankingRetriever(WrappedSpy(), reranker, config=cfg.retrieval_config)
            return ToolContext(tenant_id="t", schema="s", session=object(), retriever=retriever)

        queries = _queries(2)
        configs = [
            MatrixConfiguration(name="no_rerank", retrieval_config=RetrievalConfig(reranker_enabled=False)),
            MatrixConfiguration(name="with_rerank", retrieval_config=RetrievalConfig(reranker_enabled=True)),
        ]

        await run_matrix(queries, configs, context_factory, k=5)

        assert settings.reranker_enabled == before
        assert reranker.calls == 2  # only the with_rerank configuration's 2 queries


class TestPerQueryReproducesAggregate:
    async def test_per_query_blocks_reproduce_aggregate(self):
        tool = SpyTool(_healthy_result)
        registry = SpyRegistry(tool)
        queries = _queries(4)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        matrix = await run_matrix(queries, [config], context_factory, registry_factory=lambda: registry, k=5)
        report = build_json_report("test-set", len(queries), matrix)

        per_query_ndcg = [v["dense"]["ndcg_at_k"] for v in report["per_query"].values() if not v["dense"]["skipped"]]
        manual_mean = sum(per_query_ndcg) / len(per_query_ndcg)
        assert abs(manual_mean - report["aggregate"]["dense"]["ndcg_at_k"]) < 1e-9


class TestJsonReportFields:
    async def test_json_report_fields_complete(self):
        tool = SpyTool(_healthy_result)
        registry = SpyRegistry(tool)
        queries = _queries(2)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        matrix = await run_matrix(queries, [config], context_factory, registry_factory=lambda: registry, k=5)
        report = build_json_report("test-set", len(queries), matrix)

        for key in ("run_timestamp", "golden_set", "query_count", "configurations", "per_query", "aggregate"):
            assert key in report


class TestMarkdownSummaryRanksConfigs:
    async def test_markdown_summary_ranks_configurations(self):
        def better_result(args, context):
            return ToolResult(tool_name="semantic_retrieval", results=[
                RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
            ])

        def worse_result(args, context):
            return ToolResult(tool_name="semantic_retrieval", results=[])

        queries = _queries(3)

        good_tool = SpyTool(better_result)
        bad_tool = SpyTool(worse_result)

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        good = await run_configuration(queries, MatrixConfiguration("good", RetrievalConfig()), context_factory, registry_factory=lambda: SpyRegistry(good_tool), k=5)
        bad = await run_configuration(queries, MatrixConfiguration("bad", RetrievalConfig()), context_factory, registry_factory=lambda: SpyRegistry(bad_tool), k=5)

        matrix = MatrixResult(configurations=[good, bad])
        report = build_json_report("test-set", len(queries), matrix)
        markdown = build_markdown_summary(report)

        assert "good" in markdown
        assert "Best nDCG@k" in markdown
        assert "`good`" in markdown.split("Best nDCG@k")[1]


class TestDeterminism:
    async def test_precomputed_service_has_no_raw_text_embed_path(self):
        # embed() is the only path that would let raw text reach an external API;
        # it is intentionally unimplemented so the fixture service can never make one.
        import os
        service = PrecomputedEmbeddingService(
            os.path.join(os.path.dirname(__file__), "fixtures", "retrieval_eval", "embeddings.json"),
            expected_model="synthetic-hash-embedding-v1",
        )
        with pytest.raises(NotImplementedError):
            await service.embed("arbitrary raw query text")

    async def test_repeated_runs_are_identical(self):
        queries = _queries(4)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        run_1 = await run_configuration(queries, config, context_factory, registry_factory=lambda: SpyRegistry(SpyTool(_healthy_result)), k=5)
        run_2 = await run_configuration(queries, config, context_factory, registry_factory=lambda: SpyRegistry(SpyTool(_healthy_result)), k=5)

        assert run_1.aggregate == run_2.aggregate


# --- Orchestrated configuration (verification.md rows 58-60) ---

class ScriptedSemanticRetrievalTool:
    name = "semantic_retrieval"
    description = "scripted"
    args_schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    def __init__(self, result_fn):
        self.result_fn = result_fn

    async def call(self, args, context):
        return self.result_fn(args, context)


class ScriptedEvalPlanner:
    """Always emits one semantic_retrieval call — the orchestrator makes exactly one
    planning call per query, so there is no observe/re-plan cycle to script here."""

    def __init__(self, fail_query_ids: set[str] = frozenset()):
        self.fail_query_ids = fail_query_ids
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        last_user_msg = next(m["content"] for m in kwargs["messages"] if m["role"] == "user")
        if last_user_msg in self.fail_query_ids:
            raise RuntimeError("scripted planner failure for this query")

        tool_calls = [SimpleNamespace(id="c1", function=SimpleNamespace(name="semantic_retrieval", arguments=_json.dumps({"query": last_user_msg})))]
        message = SimpleNamespace(content=None, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class TestOrchestratedConfigurationInReport:
    """Covers verification.md row 58."""

    async def test_orchestrated_configuration_appears_alongside_baseline(self):
        baseline_tool = SpyTool(_healthy_result)
        baseline_registry = SpyRegistry(baseline_tool)

        def orchestrated_result_fn(args, context):
            return ToolResult(tool_name="semantic_retrieval", results=[
                RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
            ])

        def orchestrated_registry_factory():
            reg = ToolRegistry()
            reg.register(ScriptedSemanticRetrievalTool(orchestrated_result_fn))
            return reg

        queries = _queries(3)
        baseline_config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())
        orchestrated_config = MatrixConfiguration(
            name="orchestrated", retrieval_config=RetrievalConfig(), is_orchestrated=True,
            planner_client_factory=lambda: ScriptedEvalPlanner(),
        )

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        baseline_result = await run_configuration(queries, baseline_config, context_factory, registry_factory=lambda: baseline_registry, k=5)
        orchestrated_result = await run_configuration(queries, orchestrated_config, context_factory, registry_factory=orchestrated_registry_factory, k=5)

        report = build_json_report("test-set", len(queries), MatrixResult(configurations=[baseline_result, orchestrated_result]))

        names = {c["name"] for c in report["configurations"]}
        assert names == {"dense", "orchestrated"}
        assert report["aggregate"]["orchestrated"]["ndcg_at_k"] is not None
        assert report["aggregate"]["dense"]["ndcg_at_k"] is not None


class TestOrchestrationErrorDoesNotAbortRun:
    """Covers verification.md row 59."""

    async def test_one_failed_query_does_not_abort_the_run(self):
        def orchestrated_result_fn(args, context):
            return ToolResult(tool_name="semantic_retrieval", results=[
                RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
            ])

        def orchestrated_registry_factory():
            reg = ToolRegistry()
            reg.register(ScriptedSemanticRetrievalTool(orchestrated_result_fn))
            return reg

        queries = _queries(3)
        orchestrated_config = MatrixConfiguration(
            name="orchestrated", retrieval_config=RetrievalConfig(), is_orchestrated=True,
            planner_client_factory=lambda: ScriptedEvalPlanner(fail_query_ids={"query 1"}),
        )

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(queries, orchestrated_config, context_factory, registry_factory=orchestrated_registry_factory, k=5)

        assert len(result.per_query) == 3
        # A planner error triggers the orchestrator's degraded fallback (both
        # capabilities on the raw query), not an unrecoverable error — but the
        # fallback plan's structured_retrieval entry is unregistered here, so its
        # results are empty and the query is recorded as degraded.
        degraded = [r for r in result.per_query if r.degraded]
        assert len(degraded) == 1
        assert degraded[0].query_id == "q1"


class TestOrchestratedConfigurationFields:
    """Covers verification.md row 60."""

    def test_configuration_fields_express_budgets_not_loop_iterations(self):
        config = MatrixConfiguration(name="orchestrated", retrieval_config=RetrievalConfig())
        field_names = set(config.__dataclass_fields__)

        assert "max_invocations" in field_names
        assert "deadline_seconds" in field_names
        assert "max_iterations" not in field_names
        assert "max_tool_calls" not in field_names
        assert "observation_char_limit" not in field_names
