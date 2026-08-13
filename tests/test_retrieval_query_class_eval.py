"""Query-class evaluation coverage — verification.md rows 36, 37, 88, 89, 90, 91.

The eval suite measured chunk ranking over a synthetic shipping corpus, so the classes
the investigation actually traced — multi-condition questions, multi-document
comparisons, turns where retrieval fails — were not exercised at all. Every investigated
class now needs at least one case, and the conjunctive and multi-source planning
contract is asserted on plan SHAPE rather than on a plan-rewriting layer (design
Decision 12).
"""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from src.shared.retrieval.eval.golden_set import QUERY_CLASSES, GoldenQuery, missing_query_classes
from src.shared.retrieval.eval.metrics import Judgment as MetricJudgment
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import (
    ORCHESTRATION_SYSTEM_PROMPT,
    STRUCTURED_CAPABILITY_NAME,
    OrchestrationBudget,
    orchestrate_retrieval,
)
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext

from tests.test_retrieval_answer_eval import ANSWER_CASES, AnswerCase, evaluate_answer

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


# One case per investigated class. A class with no case fails suite validation.
QUERY_CLASS_CASES: dict[str, str] = {
    "simple_structured": "How many candidates know Python?",
    "exact_entity_lookup": "What is Mahalakshmi's email address?",
    "attribute_filtering": "Which candidates have more than 2 years of experience?",
    "multi_condition": "Find backend engineers with AWS and Kubernetes experience",
    "multi_document": "Compare Hannah and Girish",
    "ambiguous_entity": "Tell me about Sreelakshmi",
    "document_content": "Summarise what this resume says about leadership",
    "mixed": "Which candidates mention AWS, and what do their resumes say about it?",
}


def _tool_call(name, arguments, call_id="c1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class RecordingPlannerClient:
    """Captures the plan the orchestrator produced so its SHAPE can be asserted."""

    def __init__(self, tool_calls):
        self.tool_calls = tool_calls
        self.system_prompt = None
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.system_prompt = next(m["content"] for m in kwargs["messages"] if m["role"] == "system")
        message = SimpleNamespace(content=None, tool_calls=self.tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class SpyRetriever:
    def __init__(self, results=None):
        self.results = results or []

    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        return self.results


def _context_factory(retriever=None, sql_search=None):
    @asynccontextmanager
    async def factory():
        yield ToolContext(
            tenant_id="t1", schema="tenant_t1", session=object(),
            retriever=retriever, sql_search=sql_search, max_top_k=20,
        )
    return factory


async def _rows(query, session, schema, conversation_context, **_kwargs):
    return [{"document_id": "D1", "entity_value": "aws"}]


class TestPlanningContract:
    """verification.md rows 36, 37. The contract is carried by the prompt and measured
    on plan shape — no deterministic plan-rewriting layer, which would put routing logic
    back outside the planner."""

    def test_prompt_states_the_conjunctive_contract(self):
        assert "compose with AND belong in ONE invocation" in ORCHESTRATION_SYSTEM_PROMPT
        assert "intersection nothing downstream computes" in ORCHESTRATION_SYSTEM_PROMPT

    def test_prompt_states_the_multi_source_contract(self):
        assert "ENUMERATES" in ORCHESTRATION_SYSTEM_PROMPT
        assert "planned with both capabilities" in ORCHESTRATION_SYSTEM_PROMPT

    async def test_conjunctive_question_plan_shape(self):
        """A plan carrying every condition in one invocation is the passing shape; two
        independent single-condition entries is the failing one, because nothing
        downstream computes their intersection."""
        question = QUERY_CLASS_CASES["multi_condition"]
        client = RecordingPlannerClient([
            _tool_call(STRUCTURED_CAPABILITY_NAME, json.dumps({"query": question})),
        ])

        result = await orchestrate_retrieval(
            question, None, client, "gpt-4o", build_default_registry(),
            _context_factory(sql_search=_rows),
            OrchestrationBudget(max_invocations=3, deadline=float("inf")),
        )

        structured = [t for t in result.plan_trace if t.capability_name == STRUCTURED_CAPABILITY_NAME]
        assert len(structured) == 1
        assert structured[0].argument_keys == ["query"]

    async def test_split_conjunction_is_detectable_from_the_trace(self):
        """The failing shape has to be observable, or the contract cannot be measured."""
        client = RecordingPlannerClient([
            _tool_call(STRUCTURED_CAPABILITY_NAME, json.dumps({"query": "backend engineers with AWS"}), "c1"),
            _tool_call(STRUCTURED_CAPABILITY_NAME, json.dumps({"query": "backend engineers with Kubernetes"}), "c2"),
        ])

        result = await orchestrate_retrieval(
            QUERY_CLASS_CASES["multi_condition"], None, client, "gpt-4o", build_default_registry(),
            _context_factory(sql_search=_rows),
            OrchestrationBudget(max_invocations=3, deadline=float("inf")),
        )

        structured = [t for t in result.plan_trace if t.capability_name == STRUCTURED_CAPABILITY_NAME]
        assert len(structured) == 2  # the shape the contract forbids, and it is visible

    async def test_enumeration_question_plans_both_capabilities(self):
        question = QUERY_CLASS_CASES["mixed"]
        client = RecordingPlannerClient([
            _tool_call(STRUCTURED_CAPABILITY_NAME, json.dumps({"query": question}), "c1"),
            _tool_call("semantic_retrieval", json.dumps({"query": question}), "c2"),
        ])

        result = await orchestrate_retrieval(
            question, None, client, "gpt-4o", build_default_registry(),
            _context_factory(retriever=SpyRetriever([
                RetrievalResult(document_id="D1", chunk_index=0, chunk_text="aws", similarity_score=0.9),
            ]), sql_search=_rows),
            OrchestrationBudget(max_invocations=3, deadline=float("inf")),
        )

        capabilities = {t.capability_name for t in result.plan_trace}
        assert capabilities == {STRUCTURED_CAPABILITY_NAME, "semantic_retrieval"}


class TestQueryClassCoverage:
    """verification.md rows 88, 89, 90, 91."""

    def test_every_query_class_has_a_case(self):
        assert set(QUERY_CLASS_CASES) == set(QUERY_CLASSES)
        for query_class, question in QUERY_CLASS_CASES.items():
            assert question.strip(), query_class

    def test_a_class_with_no_case_fails_suite_validation(self):
        covered = [
            GoldenQuery(query_id=f"q-{c}", query=q, query_class=c)
            for c, q in QUERY_CLASS_CASES.items()
        ]
        assert missing_query_classes(covered) == []

        incomplete = [g for g in covered if g.query_class != "multi_condition"]
        assert missing_query_classes(incomplete) == ["multi_condition"]

    def test_multi_document_comparison_case_present_and_strict(self):
        """The case must fail when the reply carries evidence for only one subject —
        the exact defect multi-subject resolution fixes."""
        case = next(c for c in ANSWER_CASES if c.query_class == "multi_document")
        assert len(case.required_facts) >= 2

        one_sided = evaluate_answer(case, "Girish has 4 years of backend experience.")
        assert not one_sided.passed
        assert "hannah" in one_sided.missing_facts

        both = evaluate_answer(case, "Hannah has 3 years; Girish has 4 years.")
        assert both.passed

    async def test_multi_condition_case_records_plan_shape(self):
        question = QUERY_CLASS_CASES["multi_condition"]
        client = RecordingPlannerClient([
            _tool_call(STRUCTURED_CAPABILITY_NAME, json.dumps({"query": question})),
        ])

        result = await orchestrate_retrieval(
            question, None, client, "gpt-4o", build_default_registry(),
            _context_factory(sql_search=_rows),
            OrchestrationBudget(max_invocations=3, deadline=float("inf")),
        )

        shape = [(t.capability_name, tuple(t.argument_keys)) for t in result.plan_trace]
        assert shape == [(STRUCTURED_CAPABILITY_NAME, ("query",))]

    async def test_failed_retrieval_case_asserts_no_absence_claim(self):
        """verification.md row 90 — a turn whose structured retrieval failed must not
        come back claiming the data is absent, and the failure must be on the status."""
        async def failing_sql(query, session, schema, conversation_context, **_kwargs):
            raise RuntimeError("SQL generation failed after 3 attempt(s)")

        question = QUERY_CLASS_CASES["exact_entity_lookup"]
        client = RecordingPlannerClient([
            _tool_call(STRUCTURED_CAPABILITY_NAME, json.dumps({"query": question})),
        ])

        result = await orchestrate_retrieval(
            question, None, client, "gpt-4o", build_default_registry(),
            _context_factory(sql_search=failing_sql),
            OrchestrationBudget(max_invocations=3, deadline=float("inf")),
        )

        assert result.status.has_failure()
        structured = result.status.entries_for(STRUCTURED_CAPABILITY_NAME)
        assert [e.outcome for e in structured] == ["failed"]
        assert "SQL generation failed" in structured[0].error
        # The structured-only plan also earns one bounded semantic recovery, recorded
        # as its own entry rather than overwriting the original failure.
        assert len([e for e in result.status.entries if e.recovery]) == 1

        # And the answer-level assertion the case carries.
        case = AnswerCase(
            case_id="failed-retrieval", question=question,
            required_facts=[], facts_exist=True,
        )
        assert not evaluate_answer(case, "I couldn't find that in your data.").passed
