"""Covers verification.md rows 53-55.

ADR-001 requires zero cross-tenant leakage, and this stage is a new place where document
content leaves the process. Isolation is structural: a request is built from one
document's tokens, and nothing the model returns can redirect where a row is written."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import json

import pytest

from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.shared.config import settings

DOC_A_TOKENS = "Alpha tenant resume naming Centizen Inc. and Node.js throughout".split()
DOC_B_TOKENS = "Beta tenant resume naming Wolfdale Software and React throughout".split()


def _token_records(tokens, page_number=0):
    records = []
    offset = 0
    for token in tokens:
        records.append({
            "token": token,
            "page_number": page_number,
            "char_start": offset,
            "char_end": offset + len(token),
        })
        offset += len(token) + 1
    return records


def _entity(entity_type, value, records, word_start=0, word_end=None, confidence=0.2, page_number=0):
    end = word_end if word_end is not None else word_start
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=canonicalize(value),
        confidence=confidence,
        page_number=page_number,
        char_start=records[word_start]["char_start"],
        char_end=records[end]["char_end"],
        word_index_start=word_start,
        word_index_end=end,
    )


@pytest.fixture(autouse=True)
def stable_settings(monkeypatch):
    monkeypatch.setattr(settings, "postprocess_confidence_threshold", 0.60)
    monkeypatch.setattr(settings, "postprocess_context_chars", 1200)
    monkeypatch.setattr(settings, "max_entity_word_gap", 2)
    monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4o-mini")
    monkeypatch.setattr(settings, "postprocess_prompt_version", "v1")


class TestOneDocumentPerRequest:
    """Row 53."""

    def test_a_request_never_carries_another_document_s_text(self, monkeypatch):
        records_a = _token_records(DOC_A_TOKENS)
        records_b = _token_records(DOC_B_TOKENS)
        payloads: list[str] = []

        def _capture(system_prompt, user_payload):
            payloads.append(user_payload)
            decisions = [
                {"candidate_id": c["candidate_id"], "decision": "keep"}
                for c in json.loads(user_payload)["candidates"]
            ]
            return {"decisions": decisions}, 50

        monkeypatch.setattr(pp, "call_postprocessor", _capture)

        pp.postprocess_document(
            [_entity("COMPANY", "Centizen", records_a, word_start=4)], records_a, {}, {"COMPANY"}
        )
        pp.postprocess_document(
            [_entity("COMPANY", "Wolfdale", records_b, word_start=4)], records_b, {}, {"COMPANY"}
        )

        assert len(payloads) == 2
        assert "Wolfdale" not in payloads[0]
        assert "Centizen" not in payloads[1]

    def test_the_stage_takes_no_tenant_or_schema_argument(self):
        """Tenant scope is the worker's, resolved from server-controlled context; the
        post-processor has no way to name a schema even if it wanted to."""
        import inspect

        parameters = set(inspect.signature(pp.postprocess_document).parameters)

        assert not ({"tenant_id", "schema", "document_id"} & parameters)


class TestOutputCannotRedirectPersistence:
    """Row 54."""

    def test_document_and_tenant_fields_in_the_response_are_ignored(self, monkeypatch):
        records = _token_records(DOC_A_TOKENS)
        entities = [_entity("COMPANY", "Centizen", records, word_start=4)]

        monkeypatch.setattr(pp, "call_postprocessor", lambda s, u: ({"decisions": [{
            "candidate_id": 0,
            "decision": "modify",
            "value": "Centizen Inc.",
            "document_id": "some-other-document",
            "tenant_id": "some-other-tenant",
            "schema": "tenant_victim",
        }]}, 50))

        outcome, _ = pp.postprocess_document(entities, records, {}, {"COMPANY"})

        entity = outcome.entities[0]
        assert entity.entity_value == "Centizen Inc"
        assert not hasattr(entity, "document_id")
        assert not hasattr(entity, "tenant_id")

    def test_validated_decisions_carry_only_contract_fields(self):
        records = _token_records(DOC_A_TOKENS)
        candidates = pp.build_candidates([_entity("COMPANY", "Centizen", records, word_start=4)], [0], records)

        accepted, _ = pp.validate_decisions(
            {"decisions": [{
                "candidate_id": 0, "decision": "keep",
                "document_id": "elsewhere", "schema": "tenant_victim",
            }]},
            candidates,
            {"COMPANY"},
        )

        assert set(accepted[0]) == {"decision", "value", "entity_type", "merge_with"}

    def test_persistence_targets_are_not_derived_from_the_response(self):
        """`insert_document_entities` takes its schema and document id from the caller."""
        import inspect

        from src.extraction_service.services.document_entity_store import insert_document_entities

        parameters = list(inspect.signature(insert_document_entities).parameters)

        assert parameters[:4] == ["conn", "schema", "document_id", "entities"]


class TestEvidenceWindowIsBounded:
    """Row 55."""

    def test_the_window_never_exceeds_the_configured_budget(self, monkeypatch):
        monkeypatch.setattr(settings, "postprocess_context_chars", 60)
        long_tokens = ["filler"] * 400
        long_tokens[200] = "Centizen"
        records = _token_records(long_tokens)
        entity = _entity("COMPANY", "Centizen", records, word_start=200)

        window = pp.build_window(records, entity)

        assert len(window) <= 60

    def test_the_window_contains_the_candidate_span(self, monkeypatch):
        monkeypatch.setattr(settings, "postprocess_context_chars", 120)
        long_tokens = ["filler"] * 400
        long_tokens[200] = "Centizen"
        long_tokens[201] = "Inc."
        records = _token_records(long_tokens)
        entity = _entity("COMPANY", "Centizen Inc.", records, word_start=200, word_end=201)

        window = pp.build_window(records, entity)

        assert "Centizen Inc." in window

    def test_a_candidate_larger_than_the_budget_still_yields_its_own_span(self, monkeypatch):
        monkeypatch.setattr(settings, "postprocess_context_chars", 5)
        records = _token_records(DOC_A_TOKENS)
        entity = _entity("COMPANY", "Centizen Inc.", records, word_start=4, word_end=5)

        window = pp.build_window(records, entity)

        assert "Centizen" in window
