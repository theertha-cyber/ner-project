import pytest
from src.chat_api.services.context_assembler import ContextAssembler, SYSTEM_PROMPT, _count_tokens
from src.shared.retrieval.chunking import TOKENIZER, chunk_text
from src.shared.retrieval.models import RetrievalResult

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
