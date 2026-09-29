"""Regressions found by driving the chat bot end to end against a real tenant (resumes).

Each class pins one observed failure:

- the SQL recovery loop could never recover: after a failed attempt's raw ROLLBACK, the
  retry's `SET LOCAL search_path` ran outside a transaction and was discarded, so every
  retry failed with `relation "subject" does not exist`;
- a deliberate `LIMIT 1` ("most common language") was probed for truncation and reported
  as "1 of 13 rows — PARTIAL", so the answer refused to name the winner;
- rows without a name ("who knows Python" -> `(document_id, filename, language)`) made the
  answer drop the people whose files are called "Resume.pdf" and borrow a name from an
  unrelated passage;
- a subject already resolved to its document was still filtered with `s.name = 'Pon
  Selvakumar'` (stored as "Pon Selvakumar.A") and returned nothing;
- the semantic recovery ignored the resolved document scope and cited other candidates;
- a per-subject split where only one subject resolved scoped BOTH entries to that one;
- the planner scoped follow-ups with filenames, which matched no document id;
- "Tell me about Zanith" was declined as out-of-domain although Zanith is a candidate.
"""

import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from src.chat_api.graph import nodes as graph_nodes
from src.chat_api.services import sql_generator as sqlgen
from src.chat_api.services.sql_generator import SQLGenerator
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import (
    ORCHESTRATION_SYSTEM_PROMPT,
    OrchestrationBudget,
    PlanEntry,
    RetrievalPlan,
    _shared_document_scope,
    execute_plan,
)
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext

SCHEMA = "tenant_t1"

SURFACE = build_query_surface([
    EntityDefinitionSpec(name="PROGRAMMING_LANGUAGE", sql_identifier="e_programming_language"),
    EntityDefinitionSpec(name="NAME", sql_identifier="e_name", cardinality="single"),
])


class _Result:
    def __init__(self, rows=None, columns=None):
        self._rows = rows or []
        self._columns = columns or []

    def fetchall(self):
        return list(self._rows)

    def keys(self):
        return list(self._columns)

    def first(self):
        return self._rows[0] if self._rows else None


class RecordingSession:
    """Records statements; answers the data query with `rows` and the name lookup with
    `names` (document_id -> name)."""

    def __init__(self, rows=None, columns=None, names=None):
        self.rows = rows or []
        self.columns = columns or []
        self.names = names or {}
        self.statements: list[str] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if "AS subject_name" in sql:
            ids = (params or {}).get("ids", [])
            return _Result([
                SimpleNamespace(document_id=i, subject_name=self.names[i]) for i in ids if i in self.names
            ])
        if sql.strip().upper().startswith("SELECT"):
            return _Result(self.rows, self.columns)
        return _Result()


@pytest.mark.asyncio
class TestExecuteSqlTransactionOrder:
    async def test_begin_precedes_set_local_so_retries_keep_the_search_path(self):
        session = RecordingSession(rows=[("d1",)], columns=["document_id"])

        await SQLGenerator().execute_sql("SELECT document_id FROM subject LIMIT 100", session, SCHEMA)

        begin = session.statements.index("BEGIN READ ONLY")
        set_local = next(i for i, s in enumerate(session.statements) if s.startswith("SET LOCAL search_path"))
        assert begin < set_local


@pytest.mark.asyncio
class TestSmallLimitIsNotTruncation:
    async def test_limit_one_is_not_probed_or_reported_partial(self):
        session = RecordingSession(rows=[("python", 5)], columns=["normalized_value", "count"])
        sink: dict = {}

        await SQLGenerator().execute_sql(
            "SELECT normalized_value, COUNT(*) AS count FROM e_programming_language "
            "GROUP BY normalized_value ORDER BY count DESC LIMIT 1",
            session, SCHEMA, completeness_sink=sink,
        )

        assert not any("LIMIT 2" in s for s in session.statements)
        assert sink == {"returned": 1, "matched": 1, "truncated": False}

    async def test_default_limit_is_still_probed(self):
        session = RecordingSession(rows=[("d1",)], columns=["document_id"])

        await SQLGenerator().execute_sql(
            "SELECT document_id FROM subject LIMIT 100", session, SCHEMA, completeness_sink={},
        )

        assert any("LIMIT 101" in s for s in session.statements)


@pytest.mark.asyncio
class TestSubjectNamesAttached:
    async def test_rows_without_a_name_get_the_subjects_name(self):
        rows = [
            {"document_id": "d1", "filename": "Resume.pdf", "programming_language": "Python"},
            {"document_id": "d2", "filename": "Resume 4.pdf", "programming_language": "Python"},
            {"document_id": "d3", "filename": "Unnamed.pdf", "programming_language": "Python"},
        ]
        session = RecordingSession(names={"d1": "ZANITH KUMAR R", "d2": "Arjun Jayakumar"})

        enriched = await SQLGenerator()._attach_subject_names(rows, session, SCHEMA, SURFACE)

        assert enriched[0]["subject_name"] == "ZANITH KUMAR R"
        assert enriched[1]["subject_name"] == "Arjun Jayakumar"
        # No name extracted: left alone, never invented.
        assert "subject_name" not in enriched[2]
        assert list(enriched[0])[0] == "subject_name"

    async def test_rows_that_already_carry_the_name_are_not_looked_up(self):
        rows = [{"document_id": "d1", "name": "Hannah"}]
        session = RecordingSession(names={"d1": "Hannah Susan"})

        enriched = await SQLGenerator()._attach_subject_names(rows, session, SCHEMA, SURFACE)

        assert enriched == rows
        assert session.statements == []

    async def test_aggregate_rows_without_document_id_are_untouched(self):
        rows = [{"normalized_value": "python", "count": 5}]
        session = RecordingSession()

        assert await SQLGenerator()._attach_subject_names(rows, session, SCHEMA, SURFACE) == rows
        assert session.statements == []

    async def test_tenant_without_a_name_column_is_untouched(self):
        surface = build_query_surface([EntityDefinitionSpec(name="SKILL", sql_identifier="e_skill")])
        rows = [{"document_id": "d1"}]

        assert await SQLGenerator()._attach_subject_names(rows, RecordingSession(), SCHEMA, surface) == rows


class PromptCapturingLLM:
    def __init__(self):
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="SELECT 1"))])


async def _prompt(**kwargs) -> str:
    generator = SQLGenerator()
    generator.client = llm = PromptCapturingLLM()
    await generator.generate_sql("which companies has Pon Selvakumar worked at", surface=SURFACE, **kwargs)
    return llm.prompts[0]


@pytest.mark.asyncio
class TestSqlPromptGuidance:
    async def test_scoped_subject_is_told_not_to_filter_on_name(self):
        assert "The subject is already identified" in await _prompt(subject_scoped=True)
        assert "The subject is already identified" not in await _prompt()

    async def test_names_are_matched_loosely_and_text_is_never_cast(self):
        prompt = await _prompt()
        assert "compare a name with `=`" in prompt
        assert "Never CAST a text column to a number" in prompt
        assert "Never join two `e_…` tables" in prompt
        assert "never `LIMIT 1`" in prompt

    async def test_history_is_labelled_as_reference_material_only(self):
        prompt = await _prompt(conversation_context="user: What is Arjun's degree?")
        assert "do NOT answer them again" in prompt


class SpyRetriever:
    def __init__(self, results=None):
        self.results = results or []
        self.calls: list[tuple[str, dict | None]] = []

    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None, conversation_id=None, **_):
        self.calls.append((query, metadata_filter))
        return self.results


def _factory(retriever, sql_search):
    @asynccontextmanager
    async def factory():
        yield ToolContext(
            tenant_id="t1", schema=SCHEMA, session=object(),
            retriever=retriever, sql_search=sql_search, max_top_k=20,
        )
    return factory


def _budget():
    return OrchestrationBudget(max_invocations=3, deadline=time.monotonic() + 30)


def _chunk(doc="D1"):
    return RetrievalResult(document_id=doc, chunk_index=0, chunk_text="x", similarity_score=0.5)


class TestRecoveryScope:
    @pytest.mark.asyncio
    async def test_recovery_inherits_the_resolved_document_scope(self):
        async def empty(*_a, **_k):
            return []

        retriever = SpyRetriever([_chunk()])
        scope = {"type": "document", "document_ids": ["D1"]}
        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "q", "scope": scope}),
        ])

        await execute_plan(plan, build_default_registry(), _factory(retriever, empty), _budget(), recovery_query="q")

        assert retriever.calls == [("q", {"document_ids": ["D1"]})]

    def test_disagreeing_scopes_are_not_inherited(self):
        entries = [
            PlanEntry(capability_name="structured_retrieval",
                      arguments={"query": "a", "scope": {"type": "document", "document_ids": ["D1"]}}),
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "b"}),
        ]
        assert _shared_document_scope(entries) is None


@pytest.mark.asyncio
class TestPartialRecovery:
    async def test_an_empty_sibling_gets_one_recovery_on_its_own_query(self):
        async def per_subject(query, *_a, **_k):
            return [{"document_id": "D1", "language": "Python"}] if "Hannah" in query else []

        retriever = SpyRetriever([_chunk("D2")])
        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "languages of Hannah"}),
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "languages of Harshith"}),
        ])

        result = await execute_plan(
            plan, build_default_registry(), _factory(retriever, per_subject), _budget(),
            recovery_query="compare Hannah and Harshith",
        )

        assert [q for q, _ in retriever.calls] == ["languages of Harshith"]
        assert result.sql_results and result.chunks
        assert len([e for e in result.status.entries if e.recovery]) == 1


class TestPerEntryScoping:
    def test_split_plan_scopes_each_entry_to_its_own_mentions(self):
        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "What languages does Hannah know?"}),
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "What languages does Harshith know?"}),
        ])

        rewritten = graph_nodes._rewrite_plan_for_resolution(
            plan, ["DH"], query_override=None, mention_documents={"Hannah": ["DH"]},
        )

        assert rewritten.entries[0].arguments["scope"] == {"type": "document", "document_ids": ["DH"]}
        # Harshith did not resolve: his entry must not be narrowed to Hannah's document.
        assert "scope" not in rewritten.entries[1].arguments

    def test_single_entry_plan_still_takes_the_whole_resolved_set(self):
        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="structured_retrieval", arguments={"query": "compare Hannah and Girish"}),
        ])

        rewritten = graph_nodes._rewrite_plan_for_resolution(
            plan, ["DH", "DG"], query_override=None, mention_documents={"Hannah": ["DH"], "Girish": ["DG"]},
        )

        assert rewritten.entries[0].arguments["scope"]["document_ids"] == ["DH", "DG"]


class DocumentsSession:
    def __init__(self, documents):
        self.documents = documents  # (id, filename)

    async def execute(self, statement, params=None):
        refs = set((params or {}).get("refs", []))
        return _Result([
            SimpleNamespace(id=i, filename=f) for i, f in self.documents if i in refs or f in refs
        ])


def _session_factory(session):
    @asynccontextmanager
    async def factory():
        yield session
    return factory


@pytest.mark.asyncio
class TestPlanScopeRepair:
    async def test_filenames_are_mapped_to_document_ids_and_unknown_refs_dropped(self):
        session = DocumentsSession([("DH", "Resume - Hannah.pdf"), ("DZ", "Resume.pdf")])
        plan = RetrievalPlan(entries=[
            PlanEntry(capability_name="semantic_retrieval",
                      arguments={"query": "a", "scope": {"type": "document", "document_ids": ["Resume - Hannah.pdf"]}}),
            PlanEntry(capability_name="semantic_retrieval",
                      arguments={"query": "b", "scope": {"type": "document", "document_ids": ["nope.pdf"]}}),
            PlanEntry(capability_name="semantic_retrieval",
                      arguments={"query": "c", "scope": {"type": "document", "document_ids": ["DZ"]}}),
        ])

        repaired = await graph_nodes._repair_plan_scopes(plan, _session_factory(session), SCHEMA)

        assert repaired.entries[0].arguments["scope"]["document_ids"] == ["DH"]
        assert "scope" not in repaired.entries[1].arguments
        assert repaired.entries[2].arguments["scope"]["document_ids"] == ["DZ"]

    async def test_plan_without_scopes_is_returned_untouched(self):
        plan = RetrievalPlan(entries=[PlanEntry(capability_name="semantic_retrieval", arguments={"query": "a"})])
        assert await graph_nodes._repair_plan_scopes(plan, _session_factory(None), SCHEMA) is plan


class _Guardrails:
    def check_blocked_question_type(self, message, tenant_id):
        return None

    async def classify_domain(self, *args, **kwargs):
        return False


@pytest.mark.asyncio
class TestKnownSubjectRescuesDomainDecline:
    async def _guardrail(self, monkeypatch, outcome):
        async def fake_resolve(*_a, **_k):
            return SimpleNamespace(outcome=outcome)

        async def no_tabular(_tenant_id):
            return []

        monkeypatch.setattr(graph_nodes.entity_resolver, "resolve_entity", fake_resolve)
        monkeypatch.setattr(graph_nodes, "_tabular_sources_for_guardrail", no_tabular)
        orchestrator = SimpleNamespace(guardrails=_Guardrails(), llm_client=None, llm_model="m")
        node = graph_nodes.build_nodes(orchestrator)["guardrail"]
        return await node({
            "message": "Tell me about Zanith", "tenant_id": "t1", "schema": SCHEMA,
            "conversation_context": None, "session": object(),
        })

    async def test_message_naming_a_known_subject_is_admitted(self, monkeypatch):
        result = await self._guardrail(monkeypatch, graph_nodes.entity_resolver.UNIQUE)
        assert result == {"blocked_reason": None}

    async def test_unknown_subject_is_still_declined(self, monkeypatch):
        result = await self._guardrail(monkeypatch, graph_nodes.entity_resolver.UNRESOLVED)
        assert result["blocked_reason"] == graph_nodes.DOMAIN_DECLINE_REASON


def test_planner_prompt_preserves_intent_and_plans_the_current_question_only():
    assert "Keep the question's intent intact" in ORCHESTRATION_SYSTEM_PROMPT
    assert "Plan for the CURRENT question only" in ORCHESTRATION_SYSTEM_PROMPT
    assert "MOST RECENT list" in ORCHESTRATION_SYSTEM_PROMPT


def test_default_limit_constant_is_what_the_probe_gate_compares_against():
    assert sqlgen.DEFAULT_LIMIT == 100


class TestStructuredQueryPin:
    def _plan(self, *queries):
        return RetrievalPlan(entries=[
            PlanEntry(capability_name="structured_retrieval", arguments={"query": q}) for q in queries
        ] + [PlanEntry(capability_name="semantic_retrieval", arguments={"query": "expanded"})])

    def test_no_history_single_structured_entry_asks_the_users_question(self):
        question = "What is the most common programming language?"
        pinned = graph_nodes._pin_structured_query_to_question(
            self._plan("what programming languages do candidates know"), question, None,
        )
        assert pinned.entries[0].arguments["query"] == question
        # Semantic query expansion is kept.
        assert pinned.entries[1].arguments["query"] == "expanded"

    def test_with_history_the_planners_resolution_is_kept(self):
        plan = self._plan("What is Jane Doe's email?")
        history = [{"role": "user", "content": "Tell me about Jane Doe"}, {"role": "assistant", "content": "…"}]
        assert graph_nodes._pin_structured_query_to_question(plan, "and her email?", history) is plan

    def test_split_plans_are_left_alone(self):
        plan = self._plan("languages of A", "languages of B")
        assert graph_nodes._pin_structured_query_to_question(plan, "compare A and B", None) is plan


class TestStructuredBlockHeader:
    def test_rows_are_labelled_with_the_question_they_answer(self):
        from src.chat_api.services.context_assembler import ContextAssembler

        messages = ContextAssembler().assemble(
            "Who doesn't know Java?", [{"document_id": "d1", "subject_name": "Jane Doe"}], [], {}, None,
            structured_queries=["who doesn't know Java"],
        )
        user = messages[-1]["content"]
        assert "returned for \"who doesn't know Java\"" in user
        assert user.index("returned for") < user.index("Entity data")

    def test_no_queries_renders_the_block_unchanged(self):
        from src.chat_api.services.context_assembler import render_structured_header

        assert render_structured_header(None) == ""
        assert render_structured_header(["  "]) == ""
