import pytest

from src.extraction_service.services.entity_normalizer import (
    aggregate_confidence,
    canonicalize,
    merge_wordpieces,
    reconstruct_entities,
)


def _pred(label, token, confidence=0.9, page_number=None, char_start=None, char_end=None):
    d = {"label": label, "token": token, "confidence": confidence}
    if page_number is not None:
        d["page_number"] = page_number
    if char_start is not None:
        d["char_start"] = char_start
    if char_end is not None:
        d["char_end"] = char_end
    return d


class TestBIOReconstruction:
    """verification.md rows 1-5"""

    def test_consecutive_b_i_tokens_merge_into_one_entity(self):
        predictions = [
            _pred("B-ORG", "Computer"),
            _pred("I-ORG", "Science"),
            _pred("I-ORG", "Engineering"),
        ]
        entities = reconstruct_entities(predictions)
        assert len(entities) == 1
        assert entities[0].entity_type == "ORG"
        assert entities[0].entity_value == "Computer Science Engineering"

    def test_consecutive_b_tags_of_same_type_start_separate_entities(self):
        predictions = [_pred("B-PER", "Alice"), _pred("B-PER", "Bob")]
        entities = reconstruct_entities(predictions)
        assert [e.entity_value for e in entities] == ["Alice", "Bob"]

    def test_i_tag_of_different_type_closes_open_entity(self):
        predictions = [_pred("B-PER", "Arjun"), _pred("I-ORG", "InApp")]
        entities = reconstruct_entities(predictions)
        assert len(entities) == 2
        assert entities[0].entity_type == "PER"
        assert entities[0].entity_value == "Arjun"
        assert entities[1].entity_type == "ORG"
        assert entities[1].entity_value == "InApp"

    def test_dangling_i_tag_opens_entity_without_raising(self):
        predictions = [_pred("I-LOC", "Kerala")]
        entities = reconstruct_entities(predictions)
        assert len(entities) == 1
        assert entities[0].entity_type == "LOC"
        assert entities[0].entity_value == "Kerala"

    def test_same_entity_text_twice_produces_two_entities(self):
        predictions = [
            _pred("B-ORG", "InApp"),
            _pred("B-LOC", "Kochi"),
            _pred("B-ORG", "InApp"),
        ]
        entities = reconstruct_entities(predictions)
        org_entities = [e for e in entities if e.entity_type == "ORG"]
        assert len(org_entities) == 2
        assert all(e.entity_value == "InApp" for e in org_entities)


class TestWordPieceMerging:
    """verification.md rows 6-7"""

    def test_subword_tokens_merge_into_single_word(self):
        predictions = [
            _pred("B-PER", "A"),
            _pred("B-PER", "##r"),
            _pred("B-PER", "##jun"),
            _pred("I-PER", "Jaya"),
            _pred("I-PER", "##kumar"),
        ]
        merged = merge_wordpieces(predictions)
        entities = reconstruct_entities(merged)
        assert len(entities) == 1
        assert entities[0].entity_type == "PER"
        assert entities[0].entity_value == "Arjun Jayakumar"

    def test_whole_word_predictions_unaffected(self):
        predictions = [_pred("B-LOC", "New"), _pred("I-LOC", "York")]
        merged = merge_wordpieces(predictions)
        entities = reconstruct_entities(merged)
        assert len(entities) == 1
        assert entities[0].entity_value == "New York"


class TestConfidenceAggregation:
    """verification.md rows 8-9"""

    def test_entity_confidence_is_minimum_of_tokens(self):
        assert aggregate_confidence([0.99, 0.71, 0.88]) == pytest.approx(0.71)

    def test_single_token_entity_keeps_its_own_confidence(self):
        assert aggregate_confidence([0.93]) == pytest.approx(0.93)

    def test_reconstructed_entity_confidence_is_minimum(self):
        predictions = [
            _pred("B-ORG", "Computer", confidence=0.99),
            _pred("I-ORG", "Science", confidence=0.71),
            _pred("I-ORG", "Engineering", confidence=0.88),
        ]
        entities = reconstruct_entities(predictions)
        assert entities[0].confidence == pytest.approx(0.71)


class TestCanonicalNormalization:
    """verification.md rows 10-13"""

    def test_deterministic_fallback_normalization(self):
        assert canonicalize("Arjun  Jayakumar.") == "arjun jayakumar"

    def test_alias_map_collapses_react_variants(self):
        assert canonicalize("ReactJS") == "react"
        assert canonicalize("React.js") == "react"
        assert canonicalize("React JS") == "react"

    def test_acronym_alias_matches_expansion(self):
        assert canonicalize("Amazon Web Services") == "aws"
        assert canonicalize("AWS") == "aws"

    def test_unknown_value_falls_back_to_deterministic_normalization(self):
        assert canonicalize("InApp") == "inapp"


class TestLocationMetadata:
    """verification.md rows 14-15"""

    def test_entity_carries_offsets_spanning_first_and_last_token(self):
        predictions = [
            _pred("B-ORG", "Computer", page_number=2, char_start=100, char_end=108),
            _pred("I-ORG", "Science", page_number=2, char_start=109, char_end=116),
            _pred("I-ORG", "Engineering", page_number=2, char_start=117, char_end=128),
        ]
        entities = reconstruct_entities(predictions)
        assert entities[0].page_number == 2
        assert entities[0].char_start == 100
        assert entities[0].char_end == 128

    def test_unalignable_token_yields_null_offsets_without_raising(self):
        predictions = [_pred("B-PER", "Ghost", page_number=None, char_start=None, char_end=None)]
        entities = reconstruct_entities(predictions)
        assert len(entities) == 1
        assert entities[0].page_number is None
        assert entities[0].char_start is None
        assert entities[0].char_end is None
        assert entities[0].entity_type == "PER"
        assert entities[0].entity_value == "Ghost"
        assert entities[0].normalized_value == "ghost"
        assert entities[0].confidence == pytest.approx(0.9)


class TestReconstructionAcrossLabelVocabularies:
    """verification.md ADR-002 compliance: normalizer must reconstruct both CoNLL
    labels and a tenant's custom label_list."""

    def test_conll_labels(self):
        predictions = [_pred("B-PER", "John"), _pred("B-ORG", "Acme")]
        entities = reconstruct_entities(predictions)
        assert [e.entity_type for e in entities] == ["PER", "ORG"]

    def test_custom_tenant_label_list(self):
        predictions = [
            _pred("B-company", "Acme"),
            _pred("I-company", "Corp"),
            _pred("B-contact_details", "555-1234"),
        ]
        entities = reconstruct_entities(predictions)
        assert entities[0].entity_type == "company"
        assert entities[0].entity_value == "Acme Corp"
        assert entities[1].entity_type == "contact_details"
