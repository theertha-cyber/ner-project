"""Covers verification.md rows 34-38.

"Invalid LLM output must never be written directly to the database" is a structural
property here, not a prompt instruction: `candidate_id` is server-assigned, a malformed
batch is discarded whole, a bad item is discarded alone, and every accepted value is
re-canonicalized and re-typed by the same deterministic code every other row uses."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import json

import pytest

from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.extraction_service.services.semantic_normalizer import EntityTypeConfig
from src.shared.config import settings

WINDOW_TOKENS = (
    "Profile Having two and a half years of experience at Centizen Inc. as a "
    "Software Engineer working with Node.js and React"
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


def _entity(entity_type, value, confidence=0.2, page_number=0, word_start=0, word_end=None):
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
    def _fake_call(system_prompt, user_payload):
        return payload, tokens

    monkeypatch.setattr(pp, "call_postprocessor", _fake_call)


class TestWellFormedDecisionIsApplied:
    """Row 34."""

    def test_a_modify_backed_by_the_window_is_applied(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=10)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].entity_value == "Centizen Inc"
        assert outcome.entities[0].postprocess_status == "modified"

    def test_the_persisted_normalized_value_comes_from_canonicalize(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=10)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].normalized_value == canonicalize("Centizen Inc")

    def test_a_keep_decision_records_kept(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen Inc.", word_start=10, word_end=11)]
        _respond(monkeypatch, {"decisions": [{"candidate_id": 0, "decision": "keep"}]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].postprocess_status == "kept"
        assert outcome.entities[0].source_entity_value is None


class TestMalformedResponseDiscardsTheBatch:
    """Row 35 — and never the extraction."""

    def test_a_non_object_response_keeps_every_deterministic_entity(self, monkeypatch):
        entities = [
            _entity("COMPANY", "Centizen"),
            _entity("JOB_TITLE", "Engineer"),
        ]
        _respond(monkeypatch, ["not", "an", "object"])

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY", "JOB_TITLE"})

        assert len(outcome.entities) == 2
        assert [e.entity_value for e in outcome.entities] == ["Centizen", "Engineer"]

    def test_every_row_is_marked_failed(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen")]
        _respond(monkeypatch, {"no_decisions_here": True})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].postprocess_status == "failed"
        assert outcome.degraded is True

    def test_a_provider_failure_keeps_the_extraction(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen")]

        def _boom(system_prompt, user_payload):
            raise pp.PostprocessUnavailable("provider error: 503")

        monkeypatch.setattr(pp, "call_postprocessor", _boom)

        outcome, tokens = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].entity_value == "Centizen"
        assert outcome.entities[0].postprocess_status == "failed"
        assert outcome.degraded is True
        assert tokens == 0


class TestUnknownCandidateIdIsDiscarded:
    """Row 36."""

    def test_an_id_outside_the_request_is_ignored(self, monkeypatch):
        entities = [
            _entity("COMPANY", "Centizen", word_start=10),
            _entity("JOB_TITLE", "Engineer", word_start=15),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 99, "decision": "reject"},
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY", "JOB_TITLE"})

        assert len(outcome.entities) == 2
        assert outcome.entities[0].entity_value == "Centizen Inc"

    def test_a_duplicate_decision_for_one_candidate_is_discarded(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=10)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "keep"},
            {"candidate_id": 0, "decision": "reject"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert len(outcome.entities) == 1
        assert outcome.entities[0].postprocess_status == "kept"

    def test_candidate_ids_are_not_database_identifiers(self):
        entities = [_entity("COMPANY", "Centizen"), _entity("JOB_TITLE", "Engineer")]
        candidates = pp.build_candidates(entities, [0, 1], _token_records())

        assert [c.candidate_id for c in candidates] == [0, 1]


class TestInvalidItemDoesNotInvalidateSiblings:
    """Row 37."""

    def test_three_valid_decisions_survive_one_bad_one(self, monkeypatch):
        entities = [
            _entity("COMPANY", "Centizen", word_start=10),
            _entity("JOB_TITLE", "Software", word_start=14),
            _entity("TOOL_FRAMEWORK", "Node.js", word_start=18),
            _entity("TOOL_FRAMEWORK", "React", word_start=20),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."},
            {"candidate_id": 1, "decision": "keep"},
            {"candidate_id": 2, "decision": "modify", "value": "Kubernetes"},  # not in the window
            {"candidate_id": 3, "decision": "keep"},
        ]})

        outcome, _ = pp.postprocess_document(
            entities, _token_records(), {}, {"COMPANY", "JOB_TITLE", "TOOL_FRAMEWORK"}
        )

        by_value = {e.entity_value: e for e in outcome.entities}
        assert "Centizen Inc" in by_value
        assert by_value["Node.js"].entity_value == "Node.js"
        assert by_value["Node.js"].postprocess_status == "failed"

    def test_an_unknown_decision_verb_discards_only_its_item(self, monkeypatch):
        entities = [
            _entity("COMPANY", "Centizen", word_start=10),
            _entity("JOB_TITLE", "Software", word_start=14),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "obliterate"},
            {"candidate_id": 1, "decision": "keep"},
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY", "JOB_TITLE"})

        assert len(outcome.entities) == 2
        assert outcome.entities[0].postprocess_status == "failed"
        assert outcome.entities[1].postprocess_status == "kept"


class TestAcceptedValuesGoThroughDeterministicNormalization:
    """Row 38."""

    def test_casing_and_trailing_punctuation_are_handled_by_canonicalize(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=10)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        entity = outcome.entities[0]
        assert entity.entity_value == "Centizen Inc"
        assert entity.normalized_value == "centizen inc"

    def test_typed_values_are_rederived_by_the_semantic_normalizer(self, monkeypatch):
        entity = _entity("YEARS_OF_EXP", "two", word_start=2)
        entity.value_kind = "duration"
        entity.value_number = 2.0
        config = {"years_of_exp": EntityTypeConfig(value_kind="duration", value_unit="years")}

        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "two and a half years"}
        ]})

        outcome, _ = pp.postprocess_document([entity], _token_records(), config, {"YEARS_OF_EXP"})

        assert outcome.entities[0].entity_value == "two and a half years"
        assert outcome.entities[0].value_number == 2.5
        assert outcome.entities[0].value_unit == "years"

    def test_the_postprocessor_never_writes_to_the_database(self):
        source = open(
            os.path.join(os.path.dirname(__file__), "..", "src", "extraction_service",
                         "services", "entity_postprocessor.py"),
            encoding="utf-8",
        ).read()

        assert "INSERT INTO" not in source
        assert "insert_document_entities" not in source


class TestPromptContract:
    def test_the_prompt_names_the_allowed_types(self):
        entities = [_entity("COMPANY", "Centizen")]
        candidates = pp.build_candidates(entities, [0], _token_records())

        system, payload = pp.render_prompt(candidates, ["COMPANY", "NAME"])

        assert "COMPANY, NAME" in system
        assert json.loads(payload)["candidates"][0]["value"] == "Centizen"

    def test_an_unknown_prompt_version_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(settings, "postprocess_prompt_version", "v99")
        entities = [_entity("COMPANY", "Centizen")]
        candidates = pp.build_candidates(entities, [0], _token_records())

        with pytest.raises(pp.PostprocessUnavailable):
            pp.render_prompt(candidates, ["COMPANY"])

    def test_an_unknown_prompt_version_degrades_rather_than_raising(self, monkeypatch):
        monkeypatch.setattr(settings, "postprocess_prompt_version", "v99")
        entities = [_entity("COMPANY", "Centizen")]

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.degraded is True
        assert outcome.entities[0].entity_value == "Centizen"
