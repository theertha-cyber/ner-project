import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import (
    OUTCOME_EMPTY,
    OUTCOME_FAILED,
    OUTCOME_NOT_ATTEMPTED,
    OUTCOME_OK,
    STOP_DEADLINE,
    STOP_EMPTY_PLAN,
    STOP_PLANNER_ERROR,
    OrchestrationBudget,
    execute_plan,
    orchestrate_retrieval,
    plan_retrieval,
)
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext

pytestmark = [pytest.mark.asyncio]


def _budget(max_invocations=10, deadline_seconds=30.0) -> OrchestrationBudget:
    return OrchestrationBudget(max_invocations=max_invocations, deadline=time.monotonic() + deadline_seconds)


def _tool_call(name: str, arguments: str, call_id: str = "call-1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _planner_response(tool_calls):
    message = SimpleNamespace(content=None, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class ScriptedPlannerClient:
    """A fake AsyncOpenAI-shaped client. `plans` is a list of tool_call lists, one
    per expected `chat.completions.create` call — the orchestrator makes exactly one,
    so tests normally provide a single-element list."""

    def __init__(self, plans=None, raises: Exception | None = None):
        self.plans = plans or [[]]
        self.raises = raises
        self.call_count = 0
        self.last_kwargs = None

        async def create(**kwargs):
            self.call_count += 1
            self.last_kwargs = kwargs
            if self.raises is not None:
                raise self.raises
            tool_calls = self.plans[min(self.call_count - 1, len(self.plans) - 1)]
            return _planner_response(tool_calls)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class SpyRetriever:
    def __init__(self, results: list[RetrievalResult] | None = None, error: Exception | None = None):
        self.results = results or []
        self.error = error
        self.calls: list[dict] = []

    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        self.calls.append({"query": query, "metadata_filter": metadata_filter})
        if self.error is not None:
            raise self.error
        return self.results


def _make_chunk(document_id="D1", chunk_index=0, score=0.9) -> RetrievalResult:
    return RetrievalResult(document_id=document_id, chunk_index=chunk_index, chunk_text="text", similarity_score=score)


def _context_factory(retriever=None, sql_search=None):
    @asynccontextmanager
    async def factory():
        yield ToolContext(
            tenant_id="tenant-1", schema="tenant_test", session=object(),
            retriever=retriever, sql_search=sql_search, max_top_k=20,
        )
    return factory


# --- Plan-then-execute (rows 5-8) ---

class TestSemanticOnlyPlan:
    """Covers verification.md row 5."""

    async def test_semantic_only_plan_invokes_one_capability(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "q"}')]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        assert client.call_count == 1
        assert len(result.plan_trace) == 1
        assert result.plan_trace[0].capability_name == "semantic_retrieval"
        assert len(result.chunks) == 1
        assert result.sql_results == []
        assert result.orchestration_degraded is False


class TestBothCapabilitiesPlan:
    """Covers verification.md row 6."""

    async def test_both_capabilities_plan(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"count": 1}]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c1"),
            _tool_call("structured_retrieval", '{"query": "q"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert len(result.chunks) == 1
        assert result.sql_results == [{"count": 1}]


class TestMultiEntrySameCapability:
    """Covers verification.md row 7."""

    async def test_multi_entry_same_capability(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk(document_id="D1"), _make_chunk(document_id="D2")])

        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "part one"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "part two"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        assert len(retriever.calls) == 2
        assert len(result.plan_trace) == 2


class TestExactlyOnePlanningCall:
    """Covers verification.md row 8."""

    async def test_results_never_returned_to_planner(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "q"}')]])

        await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        assert client.call_count == 1
        # The single call's messages must not contain a tool/observation role —
        # proof that no result was ever sent back to the planner.
        messages = client.last_kwargs["messages"]
        assert all(m["role"] != "tool" for m in messages)


# --- Budgets (rows 9-11) ---

class TestInvocationCapTruncates:
    """Covers verification.md row 9."""

    async def test_invocation_cap_truncates_oversized_plan(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        calls = [_tool_call("semantic_retrieval", '{"query": "q%d"}' % i, call_id=f"c{i}") for i in range(5)]
        client = ScriptedPlannerClient(plans=[calls])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(max_invocations=3),
        )

        assert result.plan_truncated is True
        executed_count = sum(1 for t in result.plan_trace if t.executed)
        assert executed_count == 3
        rejected = [t for t in result.plan_trace if not t.executed]
        assert len(rejected) == 2
        assert all("cap" in t.rejection_reason for t in rejected)


class TestDeadlineHaltsDispatch:
    """Covers verification.md row 10."""

    async def test_deadline_halts_dispatch(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "q"}')]])
        expired_budget = OrchestrationBudget(max_invocations=10, deadline=time.monotonic() - 1)

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), expired_budget,
        )

        assert result.orchestration_stop_reason == STOP_DEADLINE
        assert retriever.calls == []
        assert all(not t.executed for t in result.plan_trace)


class TestBudgetExhaustionStillAnswers:
    """Covers verification.md row 11 (orchestrator-level slice; HTTP-level in test_chat_api_rag.py)."""

    async def test_truncated_plan_returns_partial_evidence(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk(), _make_chunk(document_id="D2")])
        calls = [_tool_call("semantic_retrieval", '{"query": "q"}', call_id=f"c{i}") for i in range(3)]
        client = ScriptedPlannerClient(plans=[calls])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(max_invocations=1),
        )

        assert not result.status.has_failure()
        assert len(result.chunks) == 2


# --- Invalid plan entries (rows 12-13) ---

class TestUnknownCapabilityDiscardedSiblingSurvives:
    """Covers verification.md row 12."""

    async def test_unknown_capability_discarded_valid_sibling_executes(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[
            _tool_call("lookup_document", '{"query": "q", "document_id": "d1"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        assert len(result.chunks) == 1
        rejected = [t for t in result.plan_trace if not t.executed]
        assert len(rejected) == 1
        assert rejected[0].capability_name == "lookup_document"
        assert "no capability registered" in rejected[0].rejection_reason


class TestInvalidArgumentsRejected:
    """Covers verification.md row 13."""

    async def test_invalid_arguments_rejected_with_named_reason(self):
        """Uses plan_retrieval + execute_plan directly (bypassing orchestrate_retrieval's
        degraded fallback) to isolate entry-level rejection: a single-entry plan where the
        only entry is invalid triggers the all-rejected fallback at the orchestrate_retrieval
        level (covered by TestEmptyPlanFallback), so this test targets the plan/execute
        layer where rejection is visible without a fallback substituting a different call."""
        registry = build_default_registry()
        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "q", "schema": "tenant_other"}'),
        ]])

        plan = await plan_retrieval("q", None, client, "gpt-4o", registry)
        result = await execute_plan(plan, registry, _context_factory(retriever=SpyRetriever()), _budget())

        assert result.plan_trace[0].executed is False
        assert "schema" in result.plan_trace[0].rejection_reason

    async def test_schema_argument_rejected_no_query_issued(self):
        """Covers verification.md row 17."""
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "x", "schema": "tenant_other"}'),
        ]])

        plan = await plan_retrieval("q", None, client, "gpt-4o", registry)
        result = await execute_plan(plan, registry, _context_factory(retriever=retriever), _budget())

        assert retriever.calls == []
        assert "schema" in result.plan_trace[0].rejection_reason


# --- Degraded fallback (rows 14-16) ---

class TestPlannerErrorFallback:
    """Covers verification.md row 14."""

    async def test_planner_error_falls_back_to_both_capabilities(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"count": 1}]

        client = ScriptedPlannerClient(raises=RuntimeError("planner down"))

        result = await orchestrate_retrieval(
            "the raw query", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert result.orchestration_degraded is True
        assert result.orchestration_stop_reason == STOP_PLANNER_ERROR
        assert len(retriever.calls) == 1
        assert retriever.calls[0]["query"] == "the raw query"
        assert result.sql_results == [{"count": 1}]


class TestEmptyPlanFallback:
    """Covers verification.md row 15."""

    async def test_empty_plan_falls_back_with_distinct_stop_reason(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        assert result.orchestration_degraded is True
        assert result.orchestration_stop_reason == STOP_EMPTY_PLAN
        assert result.orchestration_stop_reason != STOP_PLANNER_ERROR


class TestDegradationLogged:
    """Covers verification.md row 16."""

    async def test_degradation_is_logged(self, caplog):
        import logging
        registry = build_default_registry()
        client = ScriptedPlannerClient(raises=RuntimeError("planner down"))

        with caplog.at_level(logging.INFO):
            result = await orchestrate_retrieval(
                "q", None, client, "gpt-4o", registry, _context_factory(retriever=SpyRetriever()), _budget(),
            )

        assert result.orchestration_degraded is True
        assert any("degraded=True" in r.message and result.orchestration_stop_reason in r.message for r in caplog.records)


# --- Tenant scope / conversation history (rows 18-19 covered at integration level) ---

# --- Evidence accumulation (rows 20-23) ---

class TestDedupeKeepsBestScore:
    """Covers verification.md row 20. The winning occurrence is now decided by rank
    within its own invocation rather than by raw score, because two invocations' raw
    scores need not be on the same scale at all."""

    async def test_duplicate_chunks_merged_keeping_the_better_ranked_occurrence(self):
        registry = build_default_registry()
        # Second in its invocation, so rank-normalised below the other.
        weaker = RetrievalResult(document_id="D1", chunk_index=3, chunk_text="t", similarity_score=0.6)
        filler = RetrievalResult(document_id="D9", chunk_index=0, chunk_text="t", similarity_score=0.9)
        # First and only in its invocation.
        stronger = RetrievalResult(document_id="D1", chunk_index=3, chunk_text="t", similarity_score=0.8)

        class TwoCallRetriever:
            def __init__(self):
                self.n = 0

            async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
                self.n += 1
                return [filler, weaker] if self.n == 1 else [stronger]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "a"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "b"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=TwoCallRetriever()), _budget(),
        )

        merged = [c for c in result.chunks if (c.document_id, c.chunk_index) == ("D1", 3)]
        assert len(merged) == 1
        assert merged[0].similarity_score == 0.8


class TestChunksRanked:
    """Covers verification.md row 21."""

    async def test_accumulated_chunks_preserve_the_retriever_ordering(self):
        """A single invocation's ordering is the retriever's, unchanged. Re-sorting on
        the raw score would be re-ranking the reranker's output on a scale it does not
        share with anything else."""
        registry = build_default_registry()
        results = [
            RetrievalResult(document_id="D1", chunk_index=0, chunk_text="t", similarity_score=0.4),
            RetrievalResult(document_id="D2", chunk_index=0, chunk_text="t", similarity_score=0.9),
            RetrievalResult(document_id="D3", chunk_index=0, chunk_text="t", similarity_score=0.7),
        ]
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "a"}')]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=SpyRetriever(results)), _budget(),
        )

        assert [c.document_id for c in result.chunks] == ["D1", "D2", "D3"]
        assert [c.similarity_score for c in result.chunks] == [0.4, 0.9, 0.7]


class TestPartialFailureNoError:
    """Covers verification.md row 22. The old collapsed signal fired only when EVERY
    invocation of a kind failed, so a partial failure was reported as a clean run; the
    per-entry status reports both outcomes and still accumulates the good evidence."""

    async def test_partial_failure_not_reported_as_total(self):
        registry = build_default_registry()

        class FlakyRetriever:
            def __init__(self):
                self.n = 0

            async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
                self.n += 1
                if self.n == 1:
                    raise RuntimeError("boom")
                return [_make_chunk(), _make_chunk(document_id="D2")]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "a"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "b"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=FlakyRetriever()), _budget(),
        )

        assert len(result.chunks) == 2
        assert [e.outcome for e in result.status.entries] == [OUTCOME_FAILED, OUTCOME_OK]


class TestTotalFailureSetsError:
    """Covers verification.md row 23."""

    async def test_total_failure_sets_retrieval_error(self):
        registry = build_default_registry()
        retriever = SpyRetriever(error=RuntimeError("boom"))
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "a"}')]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        assert result.chunks == []
        assert result.status.has_failure()
        assert result.status.failed_capability_names() == ["semantic_retrieval"]


class TestPerInvocationRetrievalStatus:
    """Covers verification.md rows 22, 23, 24, 25, 38 — the contract that replaced
    `sql_error` / `retrieval_error`."""

    async def test_partial_structured_failure_reported_per_entry(self):
        registry = build_default_registry()
        calls = {"n": 0}

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("SQL generation failed after 3 attempt(s)")
            return [{"document_id": "D1", "entity_value": "python"}]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("structured_retrieval", '{"query": "a"}', call_id="c1"),
            _tool_call("structured_retrieval", '{"query": "b"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(sql_search=sql_search), _budget(),
        )

        outcomes = [e.outcome for e in result.status.entries]
        assert outcomes == [OUTCOME_FAILED, OUTCOME_OK]
        assert "SQL generation failed" in result.status.entries[0].error
        assert result.status.entries[1].error is None
        # The second invocation's rows survive its sibling's failure.
        assert result.sql_results == [{"document_id": "D1", "entity_value": "python"}]

    async def test_rejected_entry_reports_not_attempted(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c1"),
            _tool_call("delete_documents", '{"query": "q"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        rejected = [e for e in result.status.entries if e.capability_name == "delete_documents"]
        assert [e.outcome for e in rejected] == [OUTCOME_NOT_ATTEMPTED]
        assert rejected[0].outcome != OUTCOME_EMPTY
        assert rejected[0].reason

    async def test_zero_row_success_reports_empty_without_error(self):
        registry = build_default_registry()

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return []

        client = ScriptedPlannerClient(plans=[[_tool_call("structured_retrieval", '{"query": "q"}')]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(sql_search=sql_search), _budget(),
        )

        structured = result.status.entries_for("structured_retrieval")
        assert [e.outcome for e in structured] == [OUTCOME_EMPTY]
        assert structured[0].error is None
        # A structured-only plan that found nothing also gets one semantic recovery
        # attempt; it is a separate, clearly-marked entry, not a rewrite of this one.
        assert all(e.recovery for e in result.status.entries if e.capability_name == "semantic_retrieval")

    async def test_specific_error_text_survives_accumulation(self):
        registry = build_default_registry()

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            raise RuntimeError('relation "public.tenants" does not exist')

        client = ScriptedPlannerClient(plans=[[_tool_call("structured_retrieval", '{"query": "q"}')]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(sql_search=sql_search), _budget(),
        )

        error = result.status.entries[0].error
        assert 'relation "public.tenants" does not exist' in error
        assert "all structured_retrieval invocations failed" not in error

    async def test_plan_trace_records_shape_and_discard_reasons(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        calls = [
            _tool_call("semantic_retrieval", '{"query": "q", "top_k": 3}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q2"}', call_id="c2"),
        ]
        client = ScriptedPlannerClient(plans=[calls])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever), _budget(max_invocations=1),
        )

        assert [t.capability_name for t in result.plan_trace] == ["semantic_retrieval"] * 2
        assert result.plan_trace[0].argument_keys == ["query", "top_k"]
        assert result.plan_trace[1].executed is False
        assert "invocation cap" in result.plan_trace[1].rejection_reason
        assert result.status.entries[1].outcome == OUTCOME_NOT_ATTEMPTED


class TestCrossInvocationScoreSemantics:
    """verification.md rows 34, 35.

    The reranker falls back to unranked RRF candidates on failure, so one plan can
    produce two invocations whose scores live on incomparable scales — RRF around 0.016
    against cross-encoder logits that may be negative. Sorting those against each other
    is arbitrary; rank position is the one basis both share."""

    async def test_mixed_scale_invocations_merge_on_normalised_rank(self):
        registry = build_default_registry()

        class MixedScaleRetriever:
            def __init__(self):
                self.n = 0

            async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
                self.n += 1
                if self.n == 1:
                    # Cross-encoder logits: large, and negative for the weaker result.
                    return [
                        _make_chunk(document_id="A", chunk_index=0, score=8.2),
                        _make_chunk(document_id="A", chunk_index=1, score=-3.1),
                    ]
                # RRF fusion scores, all tiny.
                return [
                    _make_chunk(document_id="B", chunk_index=0, score=0.0163),
                    _make_chunk(document_id="B", chunk_index=1, score=0.0161),
                ]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("semantic_retrieval", '{"query": "a"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "b"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=MixedScaleRetriever()), _budget(),
        )

        ordered = [(c.document_id, c.chunk_index) for c in result.chunks]
        # Each invocation's top result outranks each invocation's second, rather than
        # the logit-scored invocation sweeping the top on scale alone.
        assert ordered[:2] == [("A", 0), ("B", 0)] or ordered[:2] == [("B", 0), ("A", 0)]
        assert set(ordered[2:]) == {("A", 1), ("B", 1)}
        # The raw score is retained for display, with the basis that produced it.
        assert {c.similarity_score for c in result.chunks} == {8.2, -3.1, 0.0163, 0.0161}
        assert all(c.score_basis for c in result.chunks)

    async def test_single_invocation_order_preserved(self):
        registry = build_default_registry()
        retriever = SpyRetriever([
            _make_chunk(document_id="D1", chunk_index=0, score=0.9),
            _make_chunk(document_id="D2", chunk_index=0, score=0.4),
            _make_chunk(document_id="D3", chunk_index=0, score=0.7),
        ])
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "q"}')]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=retriever), _budget(),
        )

        # Identical to what the retriever returned — the retriever's ordering is the
        # authority for a single invocation, scores or no scores.
        assert [c.document_id for c in result.chunks] == ["D1", "D2", "D3"]


# --- Plan trace (rows 24-25) ---

class TestTraceShape:
    """Covers verification.md row 24."""

    async def test_trace_covers_every_entry(self):
        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])
        client = ScriptedPlannerClient(plans=[[
            _tool_call("lookup_document", '{"query": "q", "document_id": "d1"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c2"),
            _tool_call("structured_retrieval", '{"query": "q"}', call_id="c3"),
        ]])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"count": 1}]

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert len(result.plan_trace) == 3
        rejected = [t for t in result.plan_trace if not t.executed]
        executed = [t for t in result.plan_trace if t.executed]
        assert len(rejected) == 1
        assert rejected[0].rejection_reason is not None
        assert rejected[0].result_count == 0
        assert len(executed) == 2
        for t in executed:
            assert t.capability_name in ("semantic_retrieval", "structured_retrieval")
            assert t.result_count >= 0
            assert t.latency_ms >= 0
        assert all("iteration" not in vars(t) for t in result.plan_trace)


class TestTraceDegradedFlag:
    """Covers verification.md row 25."""

    async def test_reranker_degradation_visible_in_trace(self):
        from src.shared.retrieval.retriever import RerankingRetriever

        class FailingReranker:
            async def rerank(self, query, results, top_k=None, jwt_token=None):
                return None

        wrapped = SpyRetriever([_make_chunk(), _make_chunk(document_id="D2")])
        reranking = RerankingRetriever(wrapped, FailingReranker())
        client = ScriptedPlannerClient(plans=[[_tool_call("semantic_retrieval", '{"query": "q"}')]])

        registry = build_default_registry()
        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry, _context_factory(retriever=reranking), _budget(),
        )

        assert result.plan_trace[0].degraded is True


# --- Planner inputs (row 2) ---

class TestPlannerInputs:
    """Covers verification.md row 2."""

    async def test_planner_receives_capability_schemas_and_history(self):
        registry = build_default_registry()
        client = ScriptedPlannerClient(plans=[[]])
        history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]

        await plan_retrieval("current question", history, client, "gpt-4o", registry)

        assert client.last_kwargs["tools"] == registry.export_schemas()
        messages = client.last_kwargs["messages"]
        contents = [m["content"] for m in messages]
        assert any("earlier question" in c for c in contents if c)
        assert any("current question" in c for c in contents if c)


# --- Candidate document filtering (normalized-entity-store rows 41-44) ---

class TestCandidateDocumentFiltering:
    """Covers verification.md rows 41-44 (normalized-entity-store change)."""

    async def test_semantic_search_scoped_to_structured_candidates(self, monkeypatch):
        from src.shared.retrieval import orchestrator as orchestrator_module

        monkeypatch.setattr(orchestrator_module.settings, "candidate_document_filtering_enabled", True)

        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk(document_id="D1"), _make_chunk(document_id="D2")])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"document_id": "D1"}, {"document_id": "D2"}]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("structured_retrieval", '{"query": "q"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert len(retriever.calls) == 1
        assert retriever.calls[0]["metadata_filter"] == {"document_ids": ["D1", "D2"]}
        assert {c.document_id for c in result.chunks} <= {"D1", "D2"}

    async def test_empty_candidate_set_leaves_semantic_retrieval_unfiltered(self, monkeypatch):
        from src.shared.retrieval import orchestrator as orchestrator_module

        monkeypatch.setattr(orchestrator_module.settings, "candidate_document_filtering_enabled", True)

        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk()])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return []

        client = ScriptedPlannerClient(plans=[[
            _tool_call("structured_retrieval", '{"query": "q"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert len(retriever.calls) == 1
        assert retriever.calls[0]["metadata_filter"] is None

    async def test_explicit_planner_scope_wins_over_candidates(self, monkeypatch):
        from src.shared.retrieval import orchestrator as orchestrator_module

        monkeypatch.setattr(orchestrator_module.settings, "candidate_document_filtering_enabled", True)

        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk(document_id="D3")])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"document_id": "D1"}]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("structured_retrieval", '{"query": "q"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q", "scope": {"type": "document", "document_ids": ["D3"]}}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert len(retriever.calls) == 1
        assert retriever.calls[0]["metadata_filter"] == {"document_ids": ["D3"]}

    async def test_feature_disabled_preserves_concurrent_execution(self, monkeypatch):
        from src.shared.retrieval import orchestrator as orchestrator_module

        monkeypatch.setattr(orchestrator_module.settings, "candidate_document_filtering_enabled", False)

        registry = build_default_registry()
        retriever = SpyRetriever([_make_chunk(document_id="D1")])

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"document_id": "D9"}]

        client = ScriptedPlannerClient(plans=[[
            _tool_call("structured_retrieval", '{"query": "q"}', call_id="c1"),
            _tool_call("semantic_retrieval", '{"query": "q"}', call_id="c2"),
        ]])

        result = await orchestrate_retrieval(
            "q", None, client, "gpt-4o", registry,
            _context_factory(retriever=retriever, sql_search=sql_search), _budget(),
        )

        assert len(retriever.calls) == 1
        assert retriever.calls[0]["metadata_filter"] is None
        assert len(result.sql_results) == 1
