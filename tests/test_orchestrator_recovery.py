"""Bounded structured-to-semantic recovery — verification.md rows 29, 30, 31, 32, 33.

The observed case: "What is Mahalakshmi's email address?" produced a structurally
correct statement that returned zero rows only because the anchor NAME entity is
missing from the extraction — while the EMAIL row and the chunk text both hold the
answer, and the plan never asked for chunks. One fixed fallback recovers that class.

It is exactly one invocation: no loop, no recursion, no second planning call.
"""

import time
from contextlib import asynccontextmanager

import pytest

from src.shared.config import settings
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import (
    OUTCOME_FAILED,
    OUTCOME_SKIPPED,
    OrchestrationBudget,
    PlanEntry,
    RetrievalPlan,
    execute_plan,
)
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

QUESTION = "What is Mahalakshmi's email address?"


class SpyRetriever:
    def __init__(self, results=None, error: Exception | None = None):
        self.results = results or []
        self.error = error
        self.calls: list[str] = []

    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        self.calls.append(query)
        if self.error is not None:
            raise self.error
        return self.results


def _chunk(document_id="D1", chunk_index=0):
    return RetrievalResult(
        document_id=document_id, chunk_index=chunk_index,
        chunk_text="mahalakshmi.s@example.com", similarity_score=0.8,
    )


def _context_factory(retriever=None, sql_search=None):
    @asynccontextmanager
    async def factory():
        yield ToolContext(
            tenant_id="t1", schema="tenant_t1", session=object(),
            retriever=retriever, sql_search=sql_search, max_top_k=20,
        )
    return factory


def _budget(max_invocations=3, seconds=30.0) -> OrchestrationBudget:
    return OrchestrationBudget(max_invocations=max_invocations, deadline=time.monotonic() + seconds)


def _structured_plan(count=1):
    return RetrievalPlan(entries=[
        PlanEntry(capability_name="structured_retrieval", arguments={"query": QUESTION})
        for _ in range(count)
    ])


async def _empty_sql(query, session, schema, conversation_context, **_kwargs):
    return []


async def _failing_sql(query, session, schema, conversation_context, **_kwargs):
    raise RuntimeError("SQL generation failed after 3 attempt(s)")


class TestRecoveryFires:
    async def test_structured_only_empty_triggers_one_semantic_recovery(self):
        retriever = SpyRetriever([_chunk()])

        result = await execute_plan(
            _structured_plan(), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_empty_sql),
            _budget(), recovery_query=QUESTION,
        )

        assert retriever.calls == [QUESTION]
        assert [c.document_id for c in result.chunks] == ["D1"]
        recovery = [e for e in result.status.entries if e.recovery]
        assert len(recovery) == 1
        assert recovery[0].capability_name == "semantic_retrieval"
        assert recovery[0].outcome == "ok"

    async def test_failed_structured_records_failure_and_recovery_separately(self):
        """verification.md row 31 — the original failure and the recovery outcome are
        two entries, not one overwritten by the other."""
        retriever = SpyRetriever([_chunk()])

        result = await execute_plan(
            _structured_plan(), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_failing_sql),
            _budget(), recovery_query=QUESTION,
        )

        structured = result.status.entries_for("structured_retrieval")
        assert [e.outcome for e in structured] == [OUTCOME_FAILED]
        assert "SQL generation failed" in structured[0].error

        recovery = [e for e in result.status.entries if e.recovery]
        assert [e.outcome for e in recovery] == ["ok"]
        assert result.chunks

    async def test_recovery_runs_at_most_once(self):
        """verification.md row 33 — a recovery that itself finds nothing does not
        trigger anything further."""
        retriever = SpyRetriever([])

        result = await execute_plan(
            _structured_plan(count=2), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_empty_sql),
            _budget(), recovery_query=QUESTION,
        )

        assert len(retriever.calls) == 1
        assert len([e for e in result.status.entries if e.recovery]) == 1
        assert result.chunks == []


class TestRecoveryDoesNotFire:
    async def test_no_recovery_when_semantic_entry_present(self):
        """verification.md row 30 — the plan already asked for chunks."""
        retriever = SpyRetriever([_chunk()])
        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="structured_retrieval", arguments={"query": QUESTION}),
            PlanEntry(capability_name="semantic_retrieval", arguments={"query": QUESTION}),
        ])

        result = await execute_plan(
            plan, build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_empty_sql),
            _budget(), recovery_query=QUESTION,
        )

        assert len(retriever.calls) == 1
        assert [e for e in result.status.entries if e.recovery] == []

    async def test_no_recovery_when_structured_returned_rows(self):
        async def rows_sql(query, session, schema, conversation_context, **_kwargs):
            return [{"document_id": "D1", "entity_value": "a@b.com"}]

        retriever = SpyRetriever([_chunk()])

        result = await execute_plan(
            _structured_plan(), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=rows_sql),
            _budget(), recovery_query=QUESTION,
        )

        assert retriever.calls == []
        assert [e for e in result.status.entries if e.recovery] == []

    async def test_no_recovery_without_a_recovery_query(self):
        retriever = SpyRetriever([_chunk()])

        result = await execute_plan(
            _structured_plan(), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_empty_sql), _budget(),
        )

        assert retriever.calls == []
        assert [e for e in result.status.entries if e.recovery] == []


class TestRecoveryBudget:
    async def test_recovery_skipped_below_min_budget_records_skip(self, monkeypatch):
        """verification.md row 32 — a skip is recorded as a skip. "We did not look" and
        "we looked and found nothing" must not reach the answer model as one thing."""
        monkeypatch.setattr(settings, "retrieval_recovery_min_budget_seconds", 5.0)
        retriever = SpyRetriever([_chunk()])

        result = await execute_plan(
            _structured_plan(), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_empty_sql),
            _budget(seconds=1.0), recovery_query=QUESTION,
        )

        assert retriever.calls == []
        recovery = [e for e in result.status.entries if e.recovery]
        assert [e.outcome for e in recovery] == [OUTCOME_SKIPPED]
        assert "budget" in recovery[0].reason
        assert result.status.has_failure_or_skip()

    async def test_recovery_counts_against_the_invocation_cap(self):
        retriever = SpyRetriever([_chunk()])

        result = await execute_plan(
            _structured_plan(count=2), build_default_registry(),
            _context_factory(retriever=retriever, sql_search=_empty_sql),
            _budget(max_invocations=2), recovery_query=QUESTION,
        )

        assert retriever.calls == []
        recovery = [e for e in result.status.entries if e.recovery]
        assert [e.outcome for e in recovery] == [OUTCOME_SKIPPED]
        assert "invocation cap" in recovery[0].reason
