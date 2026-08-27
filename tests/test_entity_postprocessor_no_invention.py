"""Covers verification.md rows 39-41 — the invention boundary.

The distinction between an evidence-supported correction and a model invention is
enforced by mechanically checking every emitted value for containment in the exact text
window the server built, not by asking the model nicely in a prompt."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.shared.config import settings

WINDOW_TOKENS = (
    "Education MCA St.Xavier’s College, Chennai and B.Sc., from Rose Mary College "
    "employed at Centizen Inc. in Bangalore"
).split()


def _token_records(tokens=WINDOW_TOKENS, page_number=0):
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


def _entity(entity_type, value, confidence=0.2, word_start=0, word_end=None, page_number=0):
    records = _token_records()
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


def _respond(monkeypatch, payload, tokens=100):
    monkeypatch.setattr(pp, "call_postprocessor", lambda s, u: (payload, tokens))


class TestUnsupportedValuesAreDiscarded:
    """Row 39."""

    def test_a_plausible_but_absent_value_is_rejected(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=13)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Acme Corporation"}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].entity_value == "Centizen"
        assert outcome.entities[0].postprocess_status == "failed"
        assert outcome.entities[0].source_entity_value is None

    def test_the_discard_is_recorded(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=13)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Acme Corporation"}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert any("not supported by the evidence window" in d for d in outcome.discarded)

    def test_a_value_from_a_different_part_of_the_document_is_rejected(self, monkeypatch):
        """The window is deliberately bounded; text outside it is not evidence."""
        entities = [_entity("COMPANY", "Centizen", word_start=13)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        accepted, discarded = pp.validate_decisions(
            {"decisions": [{"candidate_id": 0, "decision": "modify", "value": "Wolfdale Software"}]},
            candidates,
            {"COMPANY"},
        )

        assert accepted == {}
        assert discarded

    def test_an_empty_value_is_rejected(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=13)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        accepted, discarded = pp.validate_decisions(
            {"decisions": [{"candidate_id": 0, "decision": "modify", "value": "   "}]},
            candidates,
            {"COMPANY"},
        )

        assert accepted == {}


class TestPostprocessingNeverAddsEntities:
    """Row 40."""

    def test_the_entity_count_never_grows(self, monkeypatch):
        entities = [
            _entity("COMPANY", "Centizen", word_start=13),
            _entity("INSTITUTION", "College", word_start=10),
        ]
        before = len(entities)
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "keep"},
            {"candidate_id": 1, "decision": "keep"},
            {"candidate_id": 2, "decision": "modify", "value": "Bangalore"},
            {"candidate_id": 7, "decision": "modify", "value": "Chennai"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY", "INSTITUTION"})

        assert len(outcome.entities) <= before

    def test_a_reject_reduces_the_count(self, monkeypatch):
        entities = [
            _entity("COMPANY", "Centizen", word_start=13),
            _entity("INSTITUTION", "College", word_start=10),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "reject"},
            {"candidate_id": 1, "decision": "keep"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY", "INSTITUTION"})

        assert len(outcome.entities) == 1
        assert outcome.entities[0].entity_type == "INSTITUTION"

    def test_every_surviving_entity_traces_to_a_submitted_candidate(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=13)]
        originals = {id(e) for e in entities}
        _respond(monkeypatch, {"decisions": [{"candidate_id": 0, "decision": "keep"}]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert {id(e) for e in outcome.entities} <= originals


class TestFoldingDoesNotDefeatTheCheck:
    """Row 41 — a correction differing only by a curly quote is still supported."""

    def test_an_ascii_apostrophe_matches_a_curly_one_in_the_window(self, monkeypatch):
        entities = [_entity("INSTITUTION", "St.Xavier’s", word_start=2)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "St.Xavier's College"}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"INSTITUTION"})

        assert outcome.entities[0].postprocess_status == "modified"
        assert outcome.entities[0].normalized_value == "st.xavier's college"

    def test_case_differences_do_not_defeat_the_check(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=13)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "CENTIZEN INC."}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].postprocess_status == "modified"

    def test_extra_whitespace_does_not_defeat_the_check(self):
        assert pp._evidence_supported("Centizen   Inc.", "employed at Centizen Inc. in Bangalore")

    def test_a_zero_width_space_does_not_defeat_the_check(self):
        assert pp._evidence_supported("​Centizen Inc.", "employed at Centizen Inc. in Bangalore")

    def test_a_genuinely_different_word_still_fails(self):
        assert not pp._evidence_supported("Centizen Limited", "employed at Centizen Inc. in Bangalore")


class TestEvidenceWindowConstruction:
    def test_the_window_contains_the_candidate_span(self):
        records = _token_records()
        entity = _entity("COMPANY", "Centizen Inc.", word_start=13, word_end=14)

        window = pp.build_window(records, entity)

        assert "Centizen" in window

    def test_the_window_respects_the_character_budget(self, monkeypatch):
        monkeypatch.setattr(settings, "postprocess_context_chars", 40)
        records = _token_records()
        entity = _entity("COMPANY", "Centizen", word_start=13)

        window = pp.build_window(records, entity)

        assert len(window) <= 40
        assert "Centizen" in window

    def test_a_candidate_without_word_alignment_falls_back_to_its_own_value(self):
        entity = NormalizedEntity(
            entity_type="COMPANY", entity_value="Centizen", normalized_value="centizen", confidence=0.2
        )

        assert pp.build_window(_token_records(), entity) == "Centizen"
