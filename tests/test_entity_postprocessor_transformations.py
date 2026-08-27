"""Covers verification.md rows 42-47 — the permitted-transformation contract.

Operations the deterministic layer already handles are closed off so the two layers
cannot disagree, and the operations that remain are each bounded by a condition the
server checks rather than a rule the prompt states."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.extraction_service.services.semantic_normalizer import EntityTypeConfig
from src.shared.config import settings

SENTENCE = "Having two and a half years of experience HANNAH studied JAVA carrying Z5060835 today"
TOKENS = SENTENCE.split()


def _token_records(tokens=TOKENS, page_number=0):
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


def _entity(entity_type, value, confidence=0.2, word_start=0, word_end=None, page_number=0, records=None):
    records = records or _token_records()
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


class TestMergeWithinTheBound:
    """Row 42 — the `two` / `half years` shape."""

    def test_two_fragments_become_one_entity(self, monkeypatch):
        entities = [
            _entity("YEARS_OF_EXP", "two", word_start=1),
            _entity("YEARS_OF_EXP", "half years", word_start=4, word_end=5),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [1]},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"YEARS_OF_EXP"})

        assert len(outcome.entities) == 1
        assert outcome.entities[0].entity_value == "two and a half years"
        assert outcome.entities[0].postprocess_status == "merged"

    def test_the_merged_span_covers_both_fragments(self, monkeypatch):
        records = _token_records()
        entities = [
            _entity("YEARS_OF_EXP", "two", word_start=1, records=records),
            _entity("YEARS_OF_EXP", "half years", word_start=4, word_end=5, records=records),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [1]},
        ]})

        outcome, _ = pp.postprocess_document(entities, records, {}, {"YEARS_OF_EXP"})

        merged = outcome.entities[0]
        assert merged.char_start == records[1]["char_start"]
        assert merged.char_end == records[5]["char_end"]

    def test_the_merged_value_types_to_two_point_five(self, monkeypatch):
        entities = [
            _entity("YEARS_OF_EXP", "two", word_start=1),
            _entity("YEARS_OF_EXP", "half years", word_start=4, word_end=5),
        ]
        config = {"years_of_exp": EntityTypeConfig(value_kind="duration", value_unit="years")}
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [1]},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), config, {"YEARS_OF_EXP"})

        assert outcome.entities[0].value_number == 2.5
        assert outcome.entities[0].value_unit == "years"

    def test_the_original_value_is_retained_as_provenance(self, monkeypatch):
        entities = [
            _entity("YEARS_OF_EXP", "two", word_start=1),
            _entity("YEARS_OF_EXP", "half years", word_start=4, word_end=5),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [1]},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"YEARS_OF_EXP"})

        assert outcome.entities[0].source_entity_value == "two"


class TestMergeBounds:
    """Row 43 — merging is bounded exactly as BIO continuation is."""

    def test_a_cross_page_merge_is_rejected(self, monkeypatch):
        records_a = _token_records(page_number=0)
        records_b = _token_records(page_number=1)
        entities = [
            _entity("YEARS_OF_EXP", "two", word_start=1, page_number=0, records=records_a),
            _entity("YEARS_OF_EXP", "half years", word_start=4, word_end=5, page_number=1, records=records_b),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [1]},
        ]})

        outcome, _ = pp.postprocess_document(entities, records_a, {}, {"YEARS_OF_EXP"})

        assert len(outcome.entities) == 2
        assert [e.entity_value for e in outcome.entities] == ["two", "half years"]

    def test_a_merge_beyond_the_word_gap_is_rejected(self, monkeypatch):
        entities = [
            _entity("YEARS_OF_EXP", "two", word_start=1),
            _entity("YEARS_OF_EXP", "today", word_start=13),
        ]
        candidates = pp.build_candidates(entities, [0, 1], _token_records())

        accepted, discarded = pp.validate_decisions(
            {"decisions": [
                {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [1]},
            ]},
            candidates,
            {"YEARS_OF_EXP"},
        )

        assert accepted == {}
        assert any("adjacent same-page neighbour" in d for d in discarded)

    def test_a_merge_with_an_unknown_candidate_is_rejected(self):
        entities = [_entity("YEARS_OF_EXP", "two", word_start=1)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        accepted, _ = pp.validate_decisions(
            {"decisions": [
                {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": [42]},
            ]},
            candidates,
            {"YEARS_OF_EXP"},
        )

        assert accepted == {}

    def test_a_merge_with_no_targets_is_rejected(self):
        entities = [_entity("YEARS_OF_EXP", "two", word_start=1)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        accepted, _ = pp.validate_decisions(
            {"decisions": [
                {"candidate_id": 0, "decision": "merge", "value": "two and a half years", "merge_with": []},
            ]},
            candidates,
            {"YEARS_OF_EXP"},
        )

        assert accepted == {}


class TestEntityTypeCorrection:
    """Rows 44 and 45 — the largest thing only this stage can fix, bounded to the
    tenant's configured types."""

    def test_a_configured_type_is_applied(self, monkeypatch):
        entities = [_entity("COMPANY", "HANNAH", word_start=8)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "NAME"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"NAME", "COMPANY"})

        assert outcome.entities[0].entity_type == "NAME"
        assert outcome.entities[0].postprocess_status == "modified"

    def test_the_original_type_is_retained_as_provenance(self, monkeypatch):
        entities = [_entity("COMPANY", "HANNAH", word_start=8)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "NAME"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"NAME", "COMPANY"})

        assert outcome.entities[0].source_entity_type == "COMPANY"
        assert outcome.entities[0].source_entity_value is None

    def test_an_unconfigured_type_is_rejected(self, monkeypatch):
        entities = [_entity("COMPANY", "HANNAH", word_start=8)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "PERSON"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"NAME", "COMPANY"})

        assert outcome.entities[0].entity_type == "COMPANY"
        assert outcome.entities[0].postprocess_status == "failed"

    def test_the_allowed_type_check_is_case_insensitive(self, monkeypatch):
        entities = [_entity("DEGREE", "JAVA", word_start=10)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "programming_language"},
        ]})

        outcome, _ = pp.postprocess_document(
            entities, _token_records(), {}, {"PROGRAMMING_LANGUAGE", "DEGREE"}
        )

        assert outcome.entities[0].entity_type == "PROGRAMMING_LANGUAGE"

    def test_a_type_correction_alone_needs_no_value(self, monkeypatch):
        entities = [_entity("DEGREE", "JAVA", word_start=10)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "PROGRAMMING_LANGUAGE", "value": None},
        ]})

        outcome, _ = pp.postprocess_document(
            entities, _token_records(), {}, {"PROGRAMMING_LANGUAGE", "DEGREE"}
        )

        assert outcome.entities[0].entity_value == "JAVA"
        assert outcome.entities[0].entity_type == "PROGRAMMING_LANGUAGE"

    def test_a_modify_with_neither_value_nor_type_is_discarded(self):
        entities = [_entity("DEGREE", "JAVA", word_start=10)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        accepted, discarded = pp.validate_decisions(
            {"decisions": [{"candidate_id": 0, "decision": "modify"}]},
            candidates,
            {"DEGREE"},
        )

        assert accepted == {}
        assert discarded


class TestTypedValueEmissionIsIgnored:
    """Row 46 — an unverifiable number in an indexed numeric column is exactly what the
    contract forbids."""

    def test_a_returned_value_number_is_not_persisted(self, monkeypatch):
        entity = _entity("YEARS_OF_EXP", "two", word_start=1)
        config = {"years_of_exp": EntityTypeConfig(value_kind="duration", value_unit="years")}
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "two and a half years",
             "value_number": 99.0, "value_unit": "decades"},
        ]})

        outcome, _ = pp.postprocess_document([entity], _token_records(), config, {"YEARS_OF_EXP"})

        assert outcome.entities[0].value_number == 2.5
        assert outcome.entities[0].value_unit == "years"

    def test_typed_fields_are_not_read_from_the_decision(self):
        entities = [_entity("YEARS_OF_EXP", "two", word_start=1)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        accepted, _ = pp.validate_decisions(
            {"decisions": [
                {"candidate_id": 0, "decision": "modify", "value": "two and a half years",
                 "value_number": 99.0},
            ]},
            candidates,
            {"YEARS_OF_EXP"},
        )

        assert set(accepted[0]) == {"decision", "value", "entity_type", "merge_with"}


class TestRejection:
    """Row 47."""

    def test_a_rejected_candidate_produces_no_row(self, monkeypatch):
        entities = [
            _entity("PHONE_NUMBER", "Z5060835", word_start=12),
            _entity("COMPANY", "HANNAH", word_start=8),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "reject", "reason": "passport number"},
            {"candidate_id": 1, "decision": "keep"},
        ]})

        outcome, _ = pp.postprocess_document(
            entities, _token_records(), {}, {"PHONE_NUMBER", "COMPANY"}
        )

        assert [e.entity_value for e in outcome.entities] == ["HANNAH"]

    def test_rejecting_everything_leaves_no_rows(self, monkeypatch):
        entities = [_entity("PHONE_NUMBER", "Z5060835", word_start=12)]
        _respond(monkeypatch, {"decisions": [{"candidate_id": 0, "decision": "reject"}]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"PHONE_NUMBER"})

        assert outcome.entities == []


class TestClosedOffOperations:
    """Punctuation, whitespace and casing are handled deterministically, so the prompt
    must not invite the model to duplicate that work with variance."""

    def test_the_prompt_forbids_cosmetic_edits(self):
        entities = [_entity("COMPANY", "HANNAH", word_start=8)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        system, _ = pp.render_prompt(candidates, ["COMPANY"])

        assert "capitalisation, punctuation or spacing" in system

    def test_the_prompt_forbids_emitting_typed_values(self):
        entities = [_entity("COMPANY", "HANNAH", word_start=8)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        system, _ = pp.render_prompt(candidates, ["COMPANY"])

        assert "numbers, dates or units" in system

    def test_the_prompt_forbids_inventing_candidates(self):
        entities = [_entity("COMPANY", "HANNAH", word_start=8)]
        candidates = pp.build_candidates(entities, [0], _token_records())

        system, _ = pp.render_prompt(candidates, ["COMPANY"])

        assert "Never invent a candidate" in system
