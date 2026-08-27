"""Covers verification.md rows 29-33.

Post-processing every entity was measured against and rejected: on the development
tenant, 364 rows across 8 documents held four confirmed type errors, one split entity
and roughly sixteen junk rows. Sending the other 94% costs sixteen times as much for no
reachable gain, and puts correct extractions at risk of being "improved"."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.extraction_service.services.semantic_normalizer import EntityTypeConfig
from src.shared.config import settings


def _entity(entity_type, value, confidence=0.95, page_number=0, word_start=0, word_end=None, **kwargs):
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=canonicalize(value),
        confidence=confidence,
        page_number=page_number,
        char_start=word_start * 10,
        char_end=(word_end if word_end is not None else word_start) * 10 + len(value),
        word_index_start=word_start,
        word_index_end=word_end if word_end is not None else word_start,
        **kwargs,
    )


@pytest.fixture(autouse=True)
def stable_settings(monkeypatch):
    monkeypatch.setattr(settings, "postprocess_confidence_threshold", 0.60)
    monkeypatch.setattr(settings, "max_entity_word_gap", 2)
    monkeypatch.setattr(settings, "postprocess_multi_token_types", "NAME,COMPANY,INSTITUTION,ADDRESS")


class TestConfidentWellFormedEntitiesAreNotSelected:
    """Row 29."""

    def test_a_confident_multi_word_entity_is_skipped(self):
        entities = [_entity("COMPANY", "Manappuram Finance Ltd", confidence=0.97, word_start=0, word_end=2)]

        assert pp.select_candidates(entities, {}) == []

    def test_a_confident_typed_entity_with_a_value_is_skipped(self):
        entity = _entity("YEARS_OF_EXP", "5 years", confidence=0.98, word_start=0, word_end=1)
        entity.value_kind = "duration"
        entity.value_number = 5.0

        config = {"years_of_exp": EntityTypeConfig(value_kind="duration", value_unit="years")}

        assert pp.select_candidates([entity], config) == []

    def test_a_skipped_entity_keeps_the_not_applied_status(self):
        entities = [_entity("EMAIL", "arjun.jayan@gmail.com", confidence=0.99)]

        pp.select_candidates(entities, {})

        assert entities[0].postprocess_status == "not_applied"


class TestLowConfidenceSelection:
    """Row 30."""

    def test_below_the_threshold_is_selected(self):
        entities = [_entity("COMPANY", "HANNAH", confidence=0.31)]

        assert pp.select_candidates(entities, {}) == [0]

    def test_at_the_threshold_is_not_selected(self):
        entities = [_entity("COMPANY", "Centizen Inc.", confidence=0.60, word_start=0, word_end=1)]

        assert pp.select_candidates(entities, {}) == []

    def test_uncalibrated_rows_are_not_routed_by_confidence(self):
        """A raw logit of 5.63 is not on the `[0, 1]` scale the threshold is expressed
        in; comparing against one routes by noise."""
        entities = [_entity("COMPANY", "Centizen Inc.", confidence=5.63, word_start=0, word_end=1)]

        selected = pp.select_candidates(entities, {}, extraction_schema_version=1)

        assert selected == []

    def test_calibrated_rows_are_routed_by_confidence(self):
        entities = [_entity("COMPANY", "Centizen Inc.", confidence=0.20, word_start=0, word_end=1)]

        selected = pp.select_candidates(
            entities, {}, extraction_schema_version=settings.extraction_schema_version
        )

        assert selected == [0]


class TestUnparseableTypedValueSelection:
    """Row 31 — the type declares a number and the parser produced none."""

    def test_a_duration_type_with_no_typed_value_is_selected(self):
        entity = _entity("YEARS_OF_EXP", "several years", confidence=0.99, word_start=0, word_end=1)
        config = {"years_of_exp": EntityTypeConfig(value_kind="duration", value_unit="years")}

        assert pp.select_candidates([entity], config) == [0]

    def test_a_text_type_with_no_typed_value_is_not_selected(self):
        entity = _entity("SKILL", "Kubernetes", confidence=0.99)
        config = {"skill": EntityTypeConfig(value_kind="text")}

        assert pp.select_candidates([entity], config) == []

    def test_an_unconfigured_type_is_not_selected_on_this_rule(self):
        entity = _entity("MYSTERY", "Kubernetes", confidence=0.99)

        assert pp.select_candidates([entity], {}) == []


class TestSingleTokenMultiTokenTypeSelection:
    def test_a_one_word_company_is_selected(self):
        entities = [_entity("COMPANY", "VISHNU", confidence=0.99)]

        assert pp.select_candidates(entities, {}) == [0]

    def test_a_multi_word_company_is_not(self):
        entities = [_entity("COMPANY", "Wolfdale Software Solution", confidence=0.99, word_start=0, word_end=2)]

        assert pp.select_candidates(entities, {}) == []

    def test_a_one_word_type_outside_the_list_is_not_selected(self):
        entities = [_entity("PROGRAMMING_LANGUAGE", "Python", confidence=0.99)]

        assert pp.select_candidates(entities, {}) == []


class TestMergeCandidateSelection:
    """Row 32 — the `two` / `half years` shape, if reconstruction ever leaves one."""

    def test_adjacent_same_type_same_page_entities_are_both_selected(self):
        entities = [
            _entity("YEARS_OF_EXP", "two", confidence=0.99, word_start=1, word_end=1),
            _entity("YEARS_OF_EXP", "half years", confidence=0.99, word_start=4, word_end=5),
        ]

        assert pp.select_candidates(entities, {}) == [0, 1]

    def test_a_neighbour_beyond_the_gap_is_not_selected(self):
        entities = [
            _entity("COMPANY", "Alpha Beta", confidence=0.99, word_start=0, word_end=1),
            _entity("COMPANY", "Gamma Delta", confidence=0.99, word_start=20, word_end=21),
        ]

        assert pp.select_candidates(entities, {}) == []

    def test_a_neighbour_on_another_page_is_not_selected(self):
        entities = [
            _entity("COMPANY", "Alpha Beta", confidence=0.99, page_number=0, word_start=0, word_end=1),
            _entity("COMPANY", "Gamma Delta", confidence=0.99, page_number=1, word_start=3, word_end=4),
        ]

        assert pp.select_candidates(entities, {}) == []

    def test_a_neighbour_of_a_different_type_is_not_selected(self):
        entities = [
            _entity("COMPANY", "Alpha Beta", confidence=0.99, word_start=0, word_end=1),
            _entity("JOB_TITLE", "Web Developer", confidence=0.99, word_start=3, word_end=4),
        ]

        assert pp.select_candidates(entities, {}) == []


class TestCandidatesAreBatchedPerDocument:
    """Row 33."""

    def test_one_request_carries_every_candidate(self, monkeypatch):
        entities = [
            _entity("COMPANY", "HANNAH", confidence=0.20),
            _entity("DEGREE", "JAVA", confidence=0.21),
            _entity("ADDRESS", "Arjun", confidence=0.22),
            _entity("PHONE_NUMBER", "Z5060835", confidence=0.23),
            _entity("JOB_TITLE", "Engineer", confidence=0.24),
        ]
        token_records = [{"token": f"w{i}", "page_number": 0, "char_start": i * 3, "char_end": i * 3 + 2}
                         for i in range(40)]

        calls: list[str] = []

        def _fake_call(system_prompt, user_payload):
            calls.append(user_payload)
            import json as _json
            payload = _json.loads(user_payload)
            return {"decisions": [
                {"candidate_id": c["candidate_id"], "decision": "keep"} for c in payload["candidates"]
            ]}, 120

        monkeypatch.setattr(pp, "call_postprocessor", _fake_call)

        pp.postprocess_document(entities, token_records, {}, {"COMPANY", "DEGREE", "ADDRESS", "PHONE_NUMBER", "JOB_TITLE"})

        assert len(calls) == 1
        import json
        assert len(json.loads(calls[0])["candidates"]) == 5

    def test_no_call_is_made_when_nothing_is_selected(self, monkeypatch):
        def _fail(*args, **kwargs):
            raise AssertionError("no candidates means no provider call")

        monkeypatch.setattr(pp, "call_postprocessor", _fail)

        entities = [_entity("EMAIL", "arjun.jayan@gmail.com", confidence=0.99)]
        outcome, tokens = pp.postprocess_document(entities, [], {}, {"EMAIL"})

        assert outcome.entities == entities
        assert outcome.degraded is False
        assert tokens == 0
