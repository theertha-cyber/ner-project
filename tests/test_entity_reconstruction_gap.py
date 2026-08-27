"""Covers verification.md rows 12-15.

The defect: `_is_adjacent` required `word_index == prev + 1`. BERT tagged
"Having **two** and a **half years** of experience" as one entity — `B-YEARS_OF_EXP`,
`I-YEARS_OF_EXP`, `I-YEARS_OF_EXP` — but model serving filters `O` predictions, so
"and"/"a" never arrived and the two-word gap split the entity. It persisted as two rows
typing to 2.0 and 0.5 years, and `value_number >= 2.5` returned nothing."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services.entity_normalizer import reconstruct_entities
from src.extraction_service.services.semantic_normalizer import normalize_value
from src.shared.config import settings


# The real sentence, tokenized the way `worker._tokenize_span` does (whitespace).
SENTENCE_TOKENS = ["Having", "two", "and", "a", "half", "years", "of", "experience"]


def _token_records(tokens, page_number=0, start=0):
    records = []
    offset = start
    for token in tokens:
        records.append({
            "token": token,
            "page_number": page_number,
            "char_start": offset,
            "char_end": offset + len(token),
        })
        offset += len(token) + 1
    return records


def _prediction(records, word_index, label, confidence=0.9):
    record = records[word_index]
    return {
        "token": record["token"],
        "label": label,
        "confidence": confidence,
        "word_index": word_index,
        "page_number": record["page_number"],
        "char_start": record["char_start"],
        "char_end": record["char_end"],
    }


class TestBoundedGapJoinsAnEntity:
    """Row 12."""

    def test_two_word_gap_produces_one_entity(self):
        records = _token_records(SENTENCE_TOKENS)
        predictions = [
            _prediction(records, 1, "B-YEARS_OF_EXP", 4.55 / 10),
            _prediction(records, 4, "I-YEARS_OF_EXP", 4.08 / 10),
            _prediction(records, 5, "I-YEARS_OF_EXP", 5.92 / 10),
        ]

        entities = reconstruct_entities(predictions, records)

        assert len(entities) == 1
        assert entities[0].entity_type == "YEARS_OF_EXP"

    def test_value_spans_from_two_through_years(self):
        records = _token_records(SENTENCE_TOKENS)
        predictions = [
            _prediction(records, 1, "B-YEARS_OF_EXP"),
            _prediction(records, 4, "I-YEARS_OF_EXP"),
            _prediction(records, 5, "I-YEARS_OF_EXP"),
        ]

        entity = reconstruct_entities(predictions, records)[0]

        assert entity.entity_value == "two and a half years"
        assert entity.char_start == records[1]["char_start"]
        assert entity.char_end == records[5]["char_end"]

    def test_the_merged_span_types_to_two_and_a_half_years(self):
        """The point of the fix — the parser was always able to read the whole phrase."""
        records = _token_records(SENTENCE_TOKENS)
        predictions = [
            _prediction(records, 1, "B-YEARS_OF_EXP"),
            _prediction(records, 4, "I-YEARS_OF_EXP"),
            _prediction(records, 5, "I-YEARS_OF_EXP"),
        ]

        entity = reconstruct_entities(predictions, records)[0]
        structured = normalize_value(entity.entity_value, "duration", "years")

        assert structured is not None
        assert structured.number == 2.5
        assert structured.unit == "years"

    def test_without_token_records_the_labelled_tokens_are_joined(self):
        records = _token_records(SENTENCE_TOKENS)
        predictions = [
            _prediction(records, 1, "B-YEARS_OF_EXP"),
            _prediction(records, 4, "I-YEARS_OF_EXP"),
            _prediction(records, 5, "I-YEARS_OF_EXP"),
        ]

        entity = reconstruct_entities(predictions)[0]

        assert entity.entity_value == "two half years"


class TestWiderGapStillSplits:
    """Row 13."""

    def test_gap_beyond_the_bound_splits(self, monkeypatch):
        monkeypatch.setattr(settings, "max_entity_word_gap", 2)
        tokens = ["alpha"] * 12
        records = _token_records(tokens)
        predictions = [
            _prediction(records, 0, "B-COMPANY"),
            _prediction(records, 9, "I-COMPANY"),
        ]

        entities = reconstruct_entities(predictions, records)

        assert len(entities) == 2

    def test_gap_exactly_at_the_bound_joins(self, monkeypatch):
        """Two intervening words, which is the bound — the `two _and_ _a_ half` case."""
        monkeypatch.setattr(settings, "max_entity_word_gap", 2)
        records = _token_records(["a", "b", "c", "d", "e"])
        predictions = [
            _prediction(records, 0, "B-COMPANY"),
            _prediction(records, 3, "I-COMPANY"),
        ]

        assert len(reconstruct_entities(predictions, records)) == 1

    def test_gap_one_past_the_bound_splits(self, monkeypatch):
        """Three intervening words is one too many."""
        monkeypatch.setattr(settings, "max_entity_word_gap", 2)
        records = _token_records(["a", "b", "c", "d", "e"])
        predictions = [
            _prediction(records, 0, "B-COMPANY"),
            _prediction(records, 4, "I-COMPANY"),
        ]

        assert len(reconstruct_entities(predictions, records)) == 2


class TestCrossPageContinuationIsNeverStitched:
    """Row 14. This is the bug `_is_adjacent` was written to prevent, and widening the
    gap must not reopen it."""

    def _cross_page(self, gap: int):
        page_zero = _token_records(["tail"], page_number=0, start=4000)
        page_one = _token_records(["head"], page_number=1, start=0)
        predictions = [
            {**_prediction(page_zero, 0, "B-INSTITUTION"), "word_index": 100},
            {**_prediction(page_one, 0, "I-INSTITUTION"), "word_index": 100 + gap},
        ]
        return predictions

    @pytest.mark.parametrize("gap", [1, 2, 3, 40])
    def test_differing_pages_split_at_any_gap(self, gap):
        entities = reconstruct_entities(self._cross_page(gap))

        assert len(entities) == 2

    def test_neither_range_spans_both_pages(self):
        entities = reconstruct_entities(self._cross_page(1))

        assert {e.page_number for e in entities} == {0, 1}
        for entity in entities:
            assert entity.char_start is not None and entity.char_end is not None
            assert entity.char_end - entity.char_start < 100

    def test_unknown_page_fails_closed_for_a_widened_gap(self, monkeypatch):
        """A prediction the aligner could not place carries page_number None. A gap
        cannot be proven intra-page, so it splits."""
        monkeypatch.setattr(settings, "max_entity_word_gap", 2)
        predictions = [
            {"token": "Alpha", "label": "B-COMPANY", "confidence": 0.9, "word_index": 3,
             "page_number": None, "char_start": None, "char_end": None},
            {"token": "Beta", "label": "I-COMPANY", "confidence": 0.9, "word_index": 5,
             "page_number": None, "char_start": None, "char_end": None},
        ]

        assert len(reconstruct_entities(predictions)) == 2

    def test_unknown_page_still_joins_consecutive_words(self):
        """Consecutive indices never needed page metadata; that behaviour is unchanged."""
        predictions = [
            {"token": "Alpha", "label": "B-COMPANY", "confidence": 0.9, "word_index": 3,
             "page_number": None, "char_start": None, "char_end": None},
            {"token": "Beta", "label": "I-COMPANY", "confidence": 0.9, "word_index": 4,
             "page_number": None, "char_start": None, "char_end": None},
        ]

        assert len(reconstruct_entities(predictions)) == 1


class TestUnalignedPredictionsKeepExistingBehaviour:
    """Row 15: the base-model pipeline path emits WordPieces with no word alignment,
    so there is nothing to measure a gap with."""

    def test_predictions_without_word_index_join_permissively(self):
        predictions = [
            {"token": "Acme", "label": "B-ORG", "confidence": 0.9},
            {"token": "Corp", "label": "I-ORG", "confidence": 0.8},
        ]

        entities = reconstruct_entities(predictions)

        assert len(entities) == 1
        assert entities[0].entity_value == "Acme Corp"

    def test_a_differing_label_still_closes_the_entity(self):
        predictions = [
            {"token": "Acme", "label": "B-ORG", "confidence": 0.9},
            {"token": "Bangalore", "label": "I-LOC", "confidence": 0.8},
        ]

        assert len(reconstruct_entities(predictions)) == 2

    def test_an_o_prediction_still_closes_the_entity(self):
        records = _token_records(["Acme", "in", "Corp"])
        predictions = [
            _prediction(records, 0, "B-ORG"),
            _prediction(records, 1, "O"),
            _prediction(records, 2, "I-ORG"),
        ]

        assert len(reconstruct_entities(predictions, records)) == 2
