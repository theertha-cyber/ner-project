"""Covers verification.md rows 20-23.

`document_entities.normalized_value` is `NOT NULL`, which does not catch an empty
string: the development tenant stored two rows canonicalizing to `''` (from
`entity_value = ','`) and sixteen whose value was two characters or fewer. Those rows
answer nothing and appear in the entity-value samples the SQL prompt shows the
generation model."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services.entity_normalizer import (
    NormalizedEntity,
    canonicalize,
    filter_valid_entities,
    is_valid_entity,
)
from src.shared.config import settings


def _entity(entity_type: str, value: str, confidence: float = 0.9) -> NormalizedEntity:
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=canonicalize(value),
        confidence=confidence,
    )


class TestPunctuationOnlyEntitiesAreRejected:
    """Row 20."""

    def test_a_bare_comma_is_rejected(self):
        """The exact stored COMPANY row: `entity_value = ','`, `normalized_value = ''`."""
        assert is_valid_entity(_entity("COMPANY", ",")) is False

    def test_an_em_dash_job_title_is_rejected(self):
        assert is_valid_entity(_entity("JOB_TITLE", "—")) is False

    def test_bracket_noise_is_rejected(self):
        assert is_valid_entity(_entity("DEGREE", "()")) is False

    def test_the_rejection_is_counted(self):
        entities = [
            _entity("COMPANY", ","),
            _entity("COMPANY", "Centizen Inc."),
            _entity("JOB_TITLE", "—"),
        ]

        kept, rejected = filter_valid_entities(entities)

        assert [e.entity_value for e in kept] == ["Centizen Inc."]
        assert rejected == 2


class TestEmptyCanonicalValuesAreRejected:
    """Row 21."""

    def test_an_empty_canonical_value_is_rejected(self):
        entity = NormalizedEntity(
            entity_type="COMPANY", entity_value=",", normalized_value="", confidence=0.9
        )

        assert is_valid_entity(entity) is False

    def test_a_whitespace_only_canonical_value_is_rejected(self):
        entity = NormalizedEntity(
            entity_type="COMPANY", entity_value="  ", normalized_value="   ", confidence=0.9
        )

        assert is_valid_entity(entity) is False

    def test_a_zero_width_space_only_value_is_rejected(self):
        """Folding turns an all-format-character value into the empty string, which is
        exactly what makes it visible to this gate."""
        assert is_valid_entity(_entity("COMPANY", "​​")) is False

    def test_nothing_is_written_for_a_rejected_entity(self):
        kept, rejected = filter_valid_entities([_entity("COMPANY", ",")])

        assert kept == []
        assert rejected == 1


class TestConfiguredShortCodeTypesSurvive:
    """Row 22 — `C` and `R` are real languages, so the exemption is per type."""

    def test_a_single_character_programming_language_is_kept(self, monkeypatch):
        monkeypatch.setattr(settings, "entity_short_value_types", "PROGRAMMING_LANGUAGE")

        assert is_valid_entity(_entity("PROGRAMMING_LANGUAGE", "C")) is True

    def test_the_exemption_is_case_insensitive_on_the_type(self, monkeypatch):
        monkeypatch.setattr(settings, "entity_short_value_types", "programming_language")

        assert is_valid_entity(_entity("PROGRAMMING_LANGUAGE", "R")) is True

    def test_an_unexempt_type_with_the_same_value_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "entity_short_value_types", "PROGRAMMING_LANGUAGE")

        assert is_valid_entity(_entity("COMPANY", "C")) is False

    def test_multiple_exempt_types_are_parsed(self, monkeypatch):
        monkeypatch.setattr(settings, "entity_short_value_types", "PROGRAMMING_LANGUAGE, DEGREE")

        assert is_valid_entity(_entity("DEGREE", "BE")) is True

    def test_an_empty_value_is_rejected_even_for_an_exempt_type(self, monkeypatch):
        monkeypatch.setattr(settings, "entity_short_value_types", "PROGRAMMING_LANGUAGE")

        assert is_valid_entity(_entity("PROGRAMMING_LANGUAGE", ",")) is False


class TestLengthThresholdIsConfigurable:
    def test_values_at_the_threshold_are_kept(self, monkeypatch):
        monkeypatch.setattr(settings, "min_entity_value_length", 2)
        monkeypatch.setattr(settings, "entity_short_value_types", "")

        assert is_valid_entity(_entity("DEGREE", "BE")) is True

    def test_values_below_the_threshold_are_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "min_entity_value_length", 3)
        monkeypatch.setattr(settings, "entity_short_value_types", "")

        assert is_valid_entity(_entity("DEGREE", "BE")) is False


class TestRealValuesAreUnaffected:
    """The gate must not become a second source of missing entities."""

    @pytest.mark.parametrize("entity_type,value", [
        ("NAME", "ZANITH KUMAR R"),
        ("EMAIL", "arjun.jayan@gmail.com"),
        ("PHONE_NUMBER", "+91 9946651714"),
        ("COMPANY", "Manappuram Finance Ltd"),
        ("DEGREE", "B.Tech"),
        ("INSTITUTION", "College of Engineering Kallooppara"),
        ("YEARS_OF_EXP", "two and a half years"),
        ("TOOL_FRAMEWORK", "node.js"),
    ])
    def test_a_real_extracted_value_is_kept(self, entity_type, value):
        assert is_valid_entity(_entity(entity_type, value)) is True

    def test_a_mixed_batch_keeps_every_real_value(self):
        entities = [
            _entity("NAME", "GIRISH K.G"),
            _entity("COMPANY", ","),
            _entity("EMAIL", "asharshith@gmail.com"),
            _entity("JOB_TITLE", "—"),
        ]

        kept, rejected = filter_valid_entities(entities)

        assert len(kept) == 2
        assert rejected == 2

    def test_an_empty_input_reports_no_rejections(self):
        assert filter_valid_entities([]) == ([], 0)
