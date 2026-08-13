import pytest
from src.chat_api.services.context_assembler import (
    PARTIAL_ENTITY_INSTRUCTION,
    SYSTEM_PROMPT,
    ContextAssembler,
    _count_tokens,
    render_retrieval_status,
)
from src.shared.retrieval.chunking import TOKENIZER, chunk_text
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.orchestrator import (
    OUTCOME_EMPTY,
    OUTCOME_FAILED,
    OUTCOME_OK,
    OUTCOME_SKIPPED,
    CapabilityStatus,
    RetrievalStatus,
)

pytestmark = pytest.mark.verification


def _make_chunk(document_id, chunk_index, text, page_number=None):
    return RetrievalResult(
        document_id=document_id,
        chunk_index=chunk_index,
        chunk_text=text,
        similarity_score=1.0,
        page_number=page_number,
    )


def _prose(n_tokens: int) -> str:
    """Builds a run of distinct numbered words totaling exactly n_tokens under cl100k_base."""
    words = " ".join(f"tok{i}" for i in range(n_tokens * 2))
    tokens = TOKENIZER.encode(words)[:n_tokens]
    return TOKENIZER.decode(tokens)


class TestBudgetAssembly:
    def test_full_chunk_reaches_prompt_intact(self):
        """Covers scenario 1: task 2.6."""
        text = _prose(512)
        chunk = _make_chunk("doc-1", 0, text)
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [chunk], {"doc-1": "report.pdf"}, None)
        user_content = messages[-1]["content"]
        assert text in user_content

    def test_chunks_admitted_in_order_until_budget_consumed(self):
        """Covers scenario 2: task 2.7."""
        chunks = [_make_chunk(f"doc-{i}", 0, _prose(500)) for i in range(5)]
        assembler = ContextAssembler(token_budget=1200, max_chunks=5)
        messages = assembler.assemble("question?", None, chunks, {}, None)
        total = sum(_count_tokens(m["content"]) for m in messages)
        assert total <= 1200
        user_content = messages[-1]["content"]
        assert "doc-0" in user_content or chunks[0].chunk_text in user_content

    def test_oversized_chunk_skipped_not_cut(self):
        """Covers scenario 3: task 2.8."""
        oversized_text = " ".join(f"big{i}" for i in range(1500))
        oversized = _make_chunk("doc-1", 0, oversized_text)
        fitting = _make_chunk("doc-2", 0, _prose(50))
        assembler = ContextAssembler(token_budget=1000, max_chunks=5)
        messages = assembler.assemble("question?", None, [oversized, fitting], {}, None)
        user_content = messages[-1]["content"]
        assert fitting.chunk_text in user_content
        assert oversized.chunk_text not in user_content
        assert oversized.chunk_text[:100] not in user_content

    def test_oversized_first_chunk_truncated_on_token_boundary(self):
        """Covers scenario 4: task 2.9."""
        huge = _make_chunk("doc-1", 0, _prose(8000))
        assembler = ContextAssembler(token_budget=500, max_chunks=5)
        messages = assembler.assemble("question?", None, [huge], {}, None)
        user_content = messages[-1]["content"]
        assert user_content.strip() != ""
        assert "No relevant data found" not in user_content
        total = sum(_count_tokens(m["content"]) for m in messages)
        assert total <= 500

    def test_budget_accounting_includes_sql(self):
        """Covers scenario 5: task 2.10 (NER accounting removed with retrieval-time NER)."""
        chunks = [_make_chunk(f"doc-{i}", 0, _prose(400)) for i in range(3)]
        sql_results = [{"entity_type": "ORG", "count": i, "note": _prose(50)} for i in range(20)]
        assembler = ContextAssembler(token_budget=2000, max_chunks=5)
        messages = assembler.assemble("question?", sql_results, chunks, {}, None)
        total = sum(_count_tokens(m["content"]) for m in messages)
        assert total <= 2000

    def test_env_override_of_token_budget(self, monkeypatch):
        """Covers scenario 16: task 2.11."""
        monkeypatch.setenv("NER_CONTEXT_TOKEN_BUDGET", "2000")
        from src.shared.config import Settings
        scoped_settings = Settings(_env_file=None, jwt_secret="x", minio_access_key="x", minio_secret_key="x", openai_api_key="x")
        assert scoped_settings.context_token_budget == 2000

        chunks = [_make_chunk(f"doc-{i}", 0, _prose(500)) for i in range(5)]
        assembler = ContextAssembler(token_budget=scoped_settings.context_token_budget, max_chunks=5)
        messages = assembler.assemble("question?", None, chunks, {}, None)
        total = sum(_count_tokens(m["content"]) for m in messages)
        assert total <= 2000


def _unique_doc_text(n_words: int) -> str:
    return " ".join(f"tok{i}" for i in range(n_words))


def _overlap_marker(chunk_a_text: str, chunk_b_text: str) -> str:
    """Finds a word present in both chunk texts (the shared boundary region)."""
    common = set(chunk_a_text.split()) & set(chunk_b_text.split())
    assert common, "expected chunks to share overlapping text"
    return next(iter(common))


class TestDeduplication:
    def test_adjacent_chunks_deduplicated(self):
        """Covers scenario 6: task 3.4."""
        full_chunks = chunk_text(_unique_doc_text(700), chunk_size=512, overlap=128)
        assert len(full_chunks) >= 2
        c0 = _make_chunk("doc-1", full_chunks[0].chunk_index, full_chunks[0].chunk_text)
        c1 = _make_chunk("doc-1", full_chunks[1].chunk_index, full_chunks[1].chunk_text)
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [c0, c1], {}, None)
        user_content = messages[-1]["content"]
        marker = _overlap_marker(c0.chunk_text, c1.chunk_text)
        assert user_content.count(marker) == 1

    def test_dedup_survives_reranked_order(self):
        """Covers scenario 7: task 3.5."""
        full_chunks = chunk_text(_unique_doc_text(700), chunk_size=512, overlap=128)
        c0 = _make_chunk("doc-1", full_chunks[0].chunk_index, full_chunks[0].chunk_text)
        c1 = _make_chunk("doc-1", full_chunks[1].chunk_index, full_chunks[1].chunk_text)
        other = _make_chunk("doc-2", 0, _prose(50))
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [c1, other, c0], {}, None)
        user_content = messages[-1]["content"]
        marker = _overlap_marker(c0.chunk_text, c1.chunk_text)
        assert user_content.count(marker) == 1

    def test_non_adjacent_similar_chunks_preserved(self):
        """Covers scenario 8: task 3.6."""
        shared_text = _prose(100)
        c0 = _make_chunk("doc-1", 0, shared_text)
        c5 = _make_chunk("doc-1", 5, shared_text)
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [c0, c5], {}, None)
        user_content = messages[-1]["content"]
        assert user_content.count(shared_text) == 2

    def test_dedup_does_not_mutate_citation_snippets(self):
        """Covers scenario 9: task 3.7."""
        full_chunks = chunk_text("word " * 700, chunk_size=512, overlap=128)
        c0 = _make_chunk("doc-1", full_chunks[0].chunk_index, full_chunks[0].chunk_text)
        c1 = _make_chunk("doc-1", full_chunks[1].chunk_index, full_chunks[1].chunk_text)
        original_c1_text = c1.chunk_text
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        assembler.assemble("question?", None, [c0, c1], {}, None)
        assert c1.chunk_text == original_c1_text
        assert c0.chunk_text == full_chunks[0].chunk_text


class TestEmptySourceDegradation:
    """Covers task 7.3: empty-source degradation."""

    def test_all_sources_empty_produces_fallback_context(self):
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, None, None, None)
        assert "No relevant data found" in messages[-1]["content"]

    def test_empty_sql_only(self):
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        chunk = _make_chunk("doc-1", 0, _prose(20))
        messages = assembler.assemble("question?", [], [chunk], {}, None)
        assert chunk.chunk_text in messages[-1]["content"]

    def test_empty_chunks_only(self):
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        sql_results = [{"entity_type": "ORG", "count": 1}]
        messages = assembler.assemble("question?", sql_results, [], {}, None)
        assert "Entity data" in messages[-1]["content"]

    def test_no_ner_block_ever_rendered(self):
        """Retrieval-time NER is removed: the assembler has no NER input at all,
        so no response should ever contain an 'NER entities' block."""
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        chunk = _make_chunk("doc-1", 0, _prose(20))
        messages = assembler.assemble("question?", None, [chunk], {}, None)
        assert "NER entities" not in messages[-1]["content"]
        assert chunk.chunk_text in messages[-1]["content"]


class TestStructuredEvidenceTruncation:
    """verification.md rows 62-70.

    The `Entity data:` block was admitted all-or-nothing against the token budget — a
    7,944-token result set was measured disappearing whole while its citation survived
    in `sources`, and the system prompt told the model the (absent) block was
    exhaustive."""

    def _rows(self, n, width=1):
        return [{"entity_value": f"value-{i}" * width, "document_name": f"doc-{i}.pdf"} for i in range(n)]

    def test_oversized_structured_result_truncates_not_drops(self):
        rows = self._rows(60, width=20)
        assembler = ContextAssembler(token_budget=1200, max_chunks=5)

        messages, evidence = assembler.assemble(
            "question?", rows, None, {}, None, return_evidence=True,
        )
        user_content = messages[-1]["content"]

        assert "Entity data" in user_content
        assert 0 < len(evidence.rows) < len(rows)
        assert evidence.rows_truncated
        assert "PARTIAL" in user_content

    def test_fitting_structured_result_admitted_whole(self):
        rows = self._rows(5)
        messages, evidence = ContextAssembler(token_budget=6000, max_chunks=5).assemble(
            "question?", rows, None, {}, None, return_evidence=True,
        )

        assert evidence.rows == rows
        assert not evidence.rows_truncated
        assert "PARTIAL" not in messages[-1]["content"]
        assert "showing all 5 matched row(s)" in messages[-1]["content"]

    def test_structured_rows_reserved_ahead_of_chunks(self):
        """A budget too small for both must still admit structured evidence."""
        rows = self._rows(30, width=15)
        chunks = [_make_chunk(f"doc-{i}", 0, _prose(200)) for i in range(4)]
        assembler = ContextAssembler(token_budget=1300, max_chunks=4)

        messages, evidence = assembler.assemble(
            "question?", rows, chunks, {}, None, return_evidence=True,
        )

        assert len(evidence.rows) >= 1
        assert "Entity data" in messages[-1]["content"]

    def test_row_limit_truncation_suppresses_exhaustiveness_claim(self):
        rows = self._rows(100)
        messages, evidence = ContextAssembler(token_budget=60000, max_chunks=5).assemble(
            "question?", rows, None, {}, None,
            sql_completeness={"returned": 100, "matched": 142, "truncated": True},
            return_evidence=True,
        )

        system_prompt = messages[0]["content"]
        assert "PARTIAL" in messages[-1]["content"]
        assert "142" in messages[-1]["content"]
        assert PARTIAL_ENTITY_INSTRUCTION in system_prompt
        assert "authoritative and exhaustive" not in system_prompt
        assert not evidence.structured_complete

    def test_complete_result_retains_exhaustiveness_instruction(self):
        rows = self._rows(12)
        messages, evidence = ContextAssembler(token_budget=6000, max_chunks=5).assemble(
            "question?", rows, None, {}, None,
            sql_completeness={"returned": 12, "matched": 12, "truncated": False},
            return_evidence=True,
        )

        assert "authoritative and exhaustive" in messages[0]["content"]
        assert evidence.structured_complete

    def test_assembler_truncation_suppresses_claim(self):
        """Even a complete query result, trimmed here for budget, is partial evidence."""
        rows = self._rows(60, width=20)
        messages, evidence = ContextAssembler(token_budget=1200, max_chunks=5).assemble(
            "question?", rows, None, {}, None,
            sql_completeness={"returned": 60, "matched": 60, "truncated": False},
            return_evidence=True,
        )

        assert evidence.rows_truncated
        assert not evidence.structured_complete
        assert PARTIAL_ENTITY_INSTRUCTION in messages[0]["content"]

    def test_identical_rendered_rows_collapse(self):
        """The observed "Who knows AWS?" result returned four identical rows."""
        rows = [{"entity_value": "aws", "document_name": "r.pdf"}] * 4
        _, evidence = ContextAssembler(token_budget=6000, max_chunks=5).assemble(
            "question?", rows, None, {}, None, return_evidence=True,
        )

        assert evidence.rows == [{"entity_value": "aws", "document_name": "r.pdf"}]

    def test_same_value_different_documents_not_collapsed(self):
        """Provenance is exactly what makes those rows distinct."""
        rows = [
            {"entity_value": "aws", "document_name": "a.pdf"},
            {"entity_value": "aws", "document_name": "b.pdf"},
        ]
        _, evidence = ContextAssembler(token_budget=6000, max_chunks=5).assemble(
            "question?", rows, None, {}, None, return_evidence=True,
        )

        assert evidence.rows == rows

    def test_completeness_statement_uses_matched_total_after_collapse(self):
        rows = [{"entity_value": "aws"}] * 100
        messages, evidence = ContextAssembler(token_budget=6000, max_chunks=5).assemble(
            "question?", rows, None, {}, None,
            sql_completeness={"returned": 100, "matched": 142, "truncated": True},
            return_evidence=True,
        )

        # One distinct row survives the collapse, but the basis for "partial" is the
        # 142 rows the query matched, not the post-collapse count.
        assert len(evidence.rows) == 1
        assert "of 142 matched row(s)" in messages[-1]["content"]
        assert "PARTIAL" in messages[-1]["content"]

    def test_unknown_matched_total_is_stated_as_unknown(self):
        rows = self._rows(3)
        messages, _ = ContextAssembler(token_budget=6000, max_chunks=5).assemble(
            "question?", rows, None, {}, None,
            sql_completeness={"returned": 3, "matched": None, "truncated": True},
            return_evidence=True,
        )
        assert "total matched is unknown" in messages[-1]["content"]


class TestRetrievalStatusInPrompt:
    """Covers verification.md rows 26, 27, 74, 75, 76, 77.

    `sql_error` / `retrieval_error` were written on every turn and read on none, so a
    failed source reached the answer model as an absence of data and came back as
    "I couldn't find that in your data". This is the reader they never had."""

    def test_failed_structured_status_rendered_into_prompt(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(
                capability_name="structured_retrieval", outcome=OUTCOME_FAILED,
                error='relation "document_entities" does not exist',
            ),
        ])
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, None, {}, None, retrieval_status=status)
        user_content = messages[-1]["content"]

        assert "Retrieval status" in user_content
        assert "structured_retrieval" in user_content
        assert "FAILED" in user_content
        assert 'relation "document_entities" does not exist' in user_content

    def test_failure_status_statement_rendered(self):
        """The statement has to tell the model not to assert absence — that inference
        is exactly what the missing reader used to let through."""
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="semantic_retrieval", outcome=OUTCOME_FAILED, error="boom"),
        ])
        rendered = render_retrieval_status(status)
        assert rendered is not None
        assert "semantic_retrieval" in rendered
        assert "do NOT state" in rendered

    def test_clean_turn_has_no_failure_statement(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="structured_retrieval", outcome=OUTCOME_OK, result_count=3),
            CapabilityStatus(capability_name="semantic_retrieval", outcome=OUTCOME_EMPTY),
        ])
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble(
            "question?", [{"entity_type": "ORG", "count": 1}], None, {}, None, retrieval_status=status,
        )
        assert "Retrieval status" not in messages[-1]["content"]
        assert "FAILED" not in messages[-1]["content"]

    def test_clean_turn_renders_no_status_block(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="semantic_retrieval", outcome=OUTCOME_OK, result_count=2),
        ])
        assert render_retrieval_status(status) is None
        assert render_retrieval_status(None) is None

    def test_skipped_recovery_statement_rendered(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="structured_retrieval", outcome=OUTCOME_EMPTY),
            CapabilityStatus(
                capability_name="semantic_retrieval", outcome=OUTCOME_SKIPPED,
                reason="insufficient remaining budget", recovery=True,
            ),
        ])
        rendered = render_retrieval_status(status)
        assert "SKIPPED" in rendered
        assert "insufficient remaining budget" in rendered
        assert "semantic_retrieval" in rendered

    def test_degraded_planning_statement_rendered(self):
        status = RetrievalStatus(entries=[], planning_degraded=True, stop_reason="planner_error")
        rendered = render_retrieval_status(status)
        assert "DEGRADED" in rendered
        assert "planner_error" in rendered

    def test_status_block_cost_counted_in_budget(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(
                capability_name="structured_retrieval", outcome=OUTCOME_FAILED, error="boom",
            ),
        ])
        chunks = [_make_chunk(f"doc-{i}", 0, _prose(200)) for i in range(6)]
        assembler = ContextAssembler(token_budget=1400, max_chunks=6)

        with_status = assembler.assemble("question?", None, chunks, {}, None, retrieval_status=status)
        without_status = assembler.assemble("question?", None, chunks, {}, None)

        assert sum(_count_tokens(m["content"]) for m in with_status) <= 1400
        assert sum(_count_tokens(m["content"]) for m in without_status) <= 1400
        # The block is paid for out of the evidence budget, not added on top of it.
        admitted_with = sum(1 for c in chunks if c.chunk_text in with_status[-1]["content"])
        admitted_without = sum(1 for c in chunks if c.chunk_text in without_status[-1]["content"])
        assert admitted_with <= admitted_without


class TestProvenance:
    def test_chunk_labeled_with_filename_and_page(self):
        """Covers scenario 10: task 4.3."""
        chunk = _make_chunk("doc-1", 0, _prose(50), page_number=3)
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [chunk], {"doc-1": "report.pdf"}, None)
        user_content = messages[-1]["content"]
        assert "report.pdf" in user_content
        assert "page 3" in user_content
        assert "doc-1" not in user_content

    def test_chunk_without_page_number_omits_page_reference(self):
        """Covers scenario 11: task 4.4."""
        chunk = _make_chunk("doc-1", 0, _prose(50), page_number=None)
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [chunk], {"doc-1": "report.pdf"}, None)
        user_content = messages[-1]["content"]
        assert "report.pdf" in user_content
        assert "page" not in user_content

    def test_unresolvable_filename_falls_back_to_document_id(self):
        """Covers scenario 12: task 4.5."""
        chunk = _make_chunk("doc-unresolved", 0, _prose(50))
        assembler = ContextAssembler(token_budget=6000, max_chunks=5)
        messages = assembler.assemble("question?", None, [chunk], {}, None)
        user_content = messages[-1]["content"]
        assert "doc-unresolved" in user_content
