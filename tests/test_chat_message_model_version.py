import pytest
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.api.v1.schemas import Source, Citation

pytestmark = [pytest.mark.verification]


class TestAnswerKindClassification:
    def test_pending_clarification_classifies_as_clarification(self):
        result = {"pending_clarification": {"mention": "John", "candidates": []}, "blocked_reason": None}
        assert RAGOrchestrator._classify_answer_kind(result) == "clarification"

    def test_over_cap_outcome_classifies_as_clarification(self):
        result = {"pending_clarification": None, "entity_resolution_outcome": "over_cap", "blocked_reason": None}
        assert RAGOrchestrator._classify_answer_kind(result) == "clarification"

    def test_out_of_domain_blocked_reason_classifies_as_out_of_domain(self):
        result = {"pending_clarification": None, "blocked_reason": "out_of_domain"}
        assert RAGOrchestrator._classify_answer_kind(result) == "out_of_domain"

    def test_other_blocked_reason_classifies_as_guardrail_blocked(self):
        result = {"pending_clarification": None, "blocked_reason": "cross_tenant"}
        assert RAGOrchestrator._classify_answer_kind(result) == "guardrail_blocked"

    def test_pii_blocked_reason_classifies_as_guardrail_blocked(self):
        result = {"pending_clarification": None, "blocked_reason": "pii"}
        assert RAGOrchestrator._classify_answer_kind(result) == "guardrail_blocked"

    def test_no_blocking_or_clarification_classifies_as_answer(self):
        result = {"pending_clarification": None, "blocked_reason": None}
        assert RAGOrchestrator._classify_answer_kind(result) == "answer"

    def test_missing_keys_default_to_answer(self):
        assert RAGOrchestrator._classify_answer_kind({}) == "answer"


class TestModelVersionExtraction:
    def test_no_sources_returns_none(self):
        assert RAGOrchestrator._extract_model_version([]) is None

    def test_sources_without_model_version_returns_none(self):
        sources = [Source(source_type="sql", value="x"), Source(source_type="document_chunk", document_id="d1")]
        assert RAGOrchestrator._extract_model_version(sources) is None

    def test_source_with_model_version_is_returned(self):
        sources = [
            Source(source_type="sql", value="x"),
            Source(source_type="document_chunk", document_id="d1", model_version="1"),
        ]
        assert RAGOrchestrator._extract_model_version(sources) == "1"

    def test_citation_with_model_version_is_returned(self):
        sources = [Citation(document_id="d1", source_type="document_chunk", model_version="0")]
        assert RAGOrchestrator._extract_model_version(sources) == "0"

    def test_first_non_null_model_version_wins(self):
        sources = [
            Source(source_type="document_chunk", document_id="d1", model_version=None),
            Source(source_type="document_chunk", document_id="d2", model_version="2"),
        ]
        assert RAGOrchestrator._extract_model_version(sources) == "2"
