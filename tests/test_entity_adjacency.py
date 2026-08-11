"""`reconstruct_entities` used to continue an entity across an `I-` tag no matter how
far apart the two words were. Model serving drops every `O` prediction before
responding, so two labelled words pages apart arrive adjacent in the list. Observed:
'Marian Engineering College, Central' — a 35-character value carrying a 77-character
span covering unrelated text in between."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.extraction_service.services.entity_normalizer import reconstruct_entities


def _pred(token, label, word_index=None, char_start=None, char_end=None, confidence=0.9):
    pred = {"token": token, "label": label, "confidence": confidence}
    if word_index is not None:
        pred["word_index"] = word_index
    if char_start is not None:
        pred["char_start"] = char_start
        pred["char_end"] = char_end
        pred["page_number"] = 0
    return pred


class TestAdjacentContinuationStillMerges:
    def test_consecutive_word_indices_form_one_entity(self):
        entities = reconstruct_entities([
            _pred("Marian", "B-INSTITUTION", word_index=40, char_start=296, char_end=302),
            _pred("Engineering", "I-INSTITUTION", word_index=41, char_start=303, char_end=314),
            _pred("College,", "I-INSTITUTION", word_index=42, char_start=315, char_end=323),
        ])
        assert len(entities) == 1
        assert entities[0].entity_value == "Marian Engineering College,"
        assert (entities[0].char_start, entities[0].char_end) == (296, 323)


class TestGappedContinuationSplits:
    def test_same_type_across_a_word_gap_becomes_two_entities(self):
        """The observed bug: an I-INSTITUTION eleven words later got glued on."""
        entities = reconstruct_entities([
            _pred("Marian", "B-INSTITUTION", word_index=40, char_start=296, char_end=302),
            _pred("Engineering", "I-INSTITUTION", word_index=41, char_start=303, char_end=314),
            _pred("College,", "I-INSTITUTION", word_index=42, char_start=315, char_end=323),
            _pred("Central", "I-INSTITUTION", word_index=53, char_start=366, char_end=373),
        ])
        assert len(entities) == 2
        assert entities[0].entity_value == "Marian Engineering College,"
        assert entities[0].char_end == 323, "the first entity must not absorb the gap"
        assert entities[1].entity_value == "Central"
        assert (entities[1].char_start, entities[1].char_end) == (366, 373)

    def test_split_entity_keeps_its_own_type(self):
        entities = reconstruct_entities([
            _pred("Google", "B-TOOL_FRAMEWORK", word_index=10),
            _pred("Gemini", "I-TOOL_FRAMEWORK", word_index=99),
        ])
        assert [e.entity_type for e in entities] == ["TOOL_FRAMEWORK", "TOOL_FRAMEWORK"]
        assert [e.entity_value for e in entities] == ["Google", "Gemini"]

    def test_a_b_tag_still_opens_a_new_entity_regardless_of_adjacency(self):
        entities = reconstruct_entities([
            _pred("Python,", "B-PROGRAMMING_LANGUAGE", word_index=528),
            _pred("Java,", "B-PROGRAMMING_LANGUAGE", word_index=529),
        ])
        assert [e.entity_value for e in entities] == ["Python,", "Java,"]


class TestPredictionsWithoutWordIndex:
    """The base-model pipeline path emits WordPieces with no word alignment, so there
    is nothing to measure adjacency with — behaviour there must be unchanged."""

    def test_missing_word_index_keeps_permissive_merging(self):
        entities = reconstruct_entities([
            _pred("New", "B-LOC"),
            _pred("York", "I-LOC"),
        ])
        assert len(entities) == 1
        assert entities[0].entity_value == "New York"

    def test_one_side_missing_word_index_still_merges(self):
        entities = reconstruct_entities([
            _pred("New", "B-LOC", word_index=3),
            _pred("York", "I-LOC"),
        ])
        assert len(entities) == 1
        assert entities[0].entity_value == "New York"
