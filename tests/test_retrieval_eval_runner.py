import pytest

from src.shared.config import settings
from src.shared.retrieval.config import RetrievalConfig
from src.shared.retrieval.eval.embeddings import PrecomputedEmbeddingService
from src.shared.retrieval.eval.golden_set import GoldenQuery, Judgment
from src.shared.retrieval.eval.report import build_json_report, build_markdown_summary
from src.shared.retrieval.eval.runner import MatrixConfiguration, run_configuration, run_matrix
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever
from src.shared.retrieval.tools.base import ToolContext, ToolResult

pytestmark = [pytest.mark.asyncio]


def _queries(n: int) -> list[GoldenQuery]:
    return [
        GoldenQuery(query_id=f"q{i}", query=f"query {i}", relevant=[Judgment(document_id="doc-a", chunk_index=0, grade=2)])
        for i in range(n)
    ]


class SpyTool:
    name = "search_documents"

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
        assert name == "search_documents"
        return self._tool


def _healthy_result(args, context):
    return ToolResult(tool_name="search_documents", results=[
        RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
    ])


class TestRunnerInvokesToolLayer:
    """Covers verification.md row 32."""

    async def test_runner_invokes_tool_per_query(self):
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
    """Covers verification.md row 33."""

    async def test_tool_error_recorded_not_fatal(self):
        def result_fn(args, context):
            if args["query"] == "query 2":
                return ToolResult(tool_name="search_documents", results=[], error="boom")
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
        assert result.aggregate.query_count == 4


class TestMatrixPerConfigAggregates:
    """Covers verification.md row 34."""

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
    """Covers verification.md row 35."""

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
    """Covers verification.md row 36."""

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
    """Covers verification.md row 37."""

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
    """Covers verification.md row 38."""

    async def test_markdown_summary_ranks_configurations(self):
        def better_result(args, context):
            return ToolResult(tool_name="search_documents", results=[
                RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
            ])

        def worse_result(args, context):
            return ToolResult(tool_name="search_documents", results=[])

        queries = _queries(3)

        good_tool = SpyTool(better_result)
        bad_tool = SpyTool(worse_result)

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        good = await run_configuration(queries, MatrixConfiguration("good", RetrievalConfig()), context_factory, registry_factory=lambda: SpyRegistry(good_tool), k=5)
        bad = await run_configuration(queries, MatrixConfiguration("bad", RetrievalConfig()), context_factory, registry_factory=lambda: SpyRegistry(bad_tool), k=5)

        from src.shared.retrieval.eval.runner import MatrixResult
        matrix = MatrixResult(configurations=[good, bad])
        report = build_json_report("test-set", len(queries), matrix)
        markdown = build_markdown_summary(report)

        assert "good" in markdown
        assert "Best nDCG@k" in markdown
        assert "`good`" in markdown.split("Best nDCG@k")[1]


class TestDeterminism:
    """Covers verification.md rows 44-45."""

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
        tool = SpyTool(_healthy_result)
        queries = _queries(4)
        config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        run_1 = await run_configuration(queries, config, context_factory, registry_factory=lambda: SpyRegistry(SpyTool(_healthy_result)), k=5)
        run_2 = await run_configuration(queries, config, context_factory, registry_factory=lambda: SpyRegistry(SpyTool(_healthy_result)), k=5)

        assert run_1.aggregate == run_2.aggregate


# --- rows 27-28: agentic configuration in the eval harness ---

from types import SimpleNamespace
import json as _json

from src.shared.retrieval.tools.registry import ToolRegistry


class ScriptedAgenticTool:
    name = "search_documents"
    description = "scripted"
    args_schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    def __init__(self, result_fn):
        self.result_fn = result_fn

    async def call(self, args, context):
        return self.result_fn(args, context)


class ScriptedEvalPlanner:
    """Stops after one search_documents call for every query."""

    def __init__(self, fail_query_ids: set[str] = frozenset()):
        self.fail_query_ids = fail_query_ids
        self.chat = SimpleNamespace(completions=self)
        self._calls_this_query = 0

    async def create(self, **kwargs):
        # crude cycle: first call per query requests a tool, second stops.
        last_user_msg = next(m["content"] for m in kwargs["messages"] if m["role"] == "user")
        if last_user_msg in self.fail_query_ids:
            raise RuntimeError("scripted planner failure for this query")

        has_tool_message = any(m["role"] == "tool" for m in kwargs["messages"])
        if has_tool_message:
            message = SimpleNamespace(content="done", tool_calls=None)
        else:
            tool_calls = [SimpleNamespace(id="c1", function=SimpleNamespace(name="search_documents", arguments=_json.dumps({"query": last_user_msg})))]
            message = SimpleNamespace(content=None, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class TestAgenticConfigurationInReport:
    """Covers verification.md row 27."""

    async def test_agentic_configuration_appears_alongside_one_shot(self):
        one_shot_tool = SpyTool(_healthy_result)
        one_shot_registry = SpyRegistry(one_shot_tool)

        def agentic_result_fn(args, context):
            return ToolResult(tool_name="search_documents", results=[
                RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
            ])

        def agentic_registry_factory():
            reg = ToolRegistry()
            reg.register(ScriptedAgenticTool(agentic_result_fn))
            return reg

        queries = _queries(3)
        one_shot_config = MatrixConfiguration(name="dense", retrieval_config=RetrievalConfig())
        agentic_config = MatrixConfiguration(
            name="agentic", retrieval_config=RetrievalConfig(), is_agentic=True,
            planner_client_factory=lambda: ScriptedEvalPlanner(),
        )

        def one_shot_context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        def agentic_context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        one_shot_result = await run_configuration(queries, one_shot_config, one_shot_context_factory, registry_factory=lambda: one_shot_registry, k=5)
        agentic_result = await run_configuration(queries, agentic_config, agentic_context_factory, registry_factory=agentic_registry_factory, k=5)

        report = build_json_report("test-set", len(queries), _make_matrix([one_shot_result, agentic_result]))

        names = {c["name"] for c in report["configurations"]}
        assert names == {"dense", "agentic"}
        assert report["aggregate"]["agentic"]["ndcg_at_k"] is not None
        assert report["aggregate"]["dense"]["ndcg_at_k"] is not None


class TestAgenticQueryErrorDoesNotAbortRun:
    """Covers verification.md row 28."""

    async def test_one_failed_query_does_not_abort_the_run(self):
        def agentic_result_fn(args, context):
            return ToolResult(tool_name="search_documents", results=[
                RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="c", similarity_score=0.9)
            ])

        def agentic_registry_factory():
            reg = ToolRegistry()
            reg.register(ScriptedAgenticTool(agentic_result_fn))
            return reg

        queries = _queries(3)
        agentic_config = MatrixConfiguration(
            name="agentic", retrieval_config=RetrievalConfig(), is_agentic=True,
            planner_client_factory=lambda: ScriptedEvalPlanner(fail_query_ids={"query 1"}),
        )

        def context_factory(cfg, query):
            return ToolContext(tenant_id="t", schema="s", session=object())

        result = await run_configuration(queries, agentic_config, context_factory, registry_factory=agentic_registry_factory, k=5)

        assert len(result.per_query) == 3
        failed = [r for r in result.per_query if r.error]
        assert len(failed) == 1
        assert result.aggregate.query_count == 2


def _make_matrix(config_results):
    from src.shared.retrieval.eval.runner import MatrixResult
    return MatrixResult(configurations=config_results)
