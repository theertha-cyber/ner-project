"""Covers verification.md rows 16-19.

`worker._tokenize_span` splits on `\\S+`, so punctuation binds to the word before the
model ever sees it — 181 of 364 stored values on the development tenant ended in
`.,;:)`. Trimming the reconstructed value without moving `char_start`/`char_end` would
leave the offsets over-reaching the text they name, so the two must move together."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services.entity_normalizer import reconstruct_entities, trim_span


def _records_from_text(source: str, page_number=0):
    """Whitespace tokenization with real offsets, matching `worker._tokenize_span`."""
    import re

    return [
        {
            "token": m.group(0),
            "page_number": page_number,
            "char_start": m.start(),
            "char_end": m.end(),
        }
        for m in re.finditer(r"\S+", source)
    ]


def _predict(records, indices, label_type):
    predictions = []
    for position, index in enumerate(indices):
        record = records[index]
        predictions.append({
            "token": record["token"],
            "label": f"{'B' if position == 0 else 'I'}-{label_type}",
            "confidence": 0.9,
            "word_index": index,
            "page_number": record["page_number"],
            "char_start": record["char_start"],
            "char_end": record["char_end"],
        })
    return predictions


class TestTrimSpanHelper:
    def test_returns_the_characters_removed_from_each_end(self):
        assert trim_span("Centizen Inc.,") == ("Centizen Inc", 0, 2)

    def test_leading_punctuation_is_counted_separately(self):
        assert trim_span("(CSE)") == ("CSE", 1, 1)

    def test_nothing_to_trim_reports_zero(self):
        assert trim_span("Centizen Inc") == ("Centizen Inc", 0, 0)

    def test_all_punctuation_trims_to_empty(self):
        trimmed, left, right = trim_span(",")
        assert trimmed == ""
        assert left + right == 1


class TestTrailingPunctuationMovesTheEndOffset:
    """Row 16."""

    def test_trailing_comma_and_period_are_removed_and_char_end_moves(self):
        source = " " * 100 + "Centizen Inc.,"
        records = _records_from_text(source)
        assert records[0]["char_start"] == 100 and records[-1]["char_end"] == 114

        entity = reconstruct_entities(_predict(records, [0, 1], "COMPANY"), records)[0]

        assert entity.entity_value == "Centizen Inc"
        assert entity.char_start == 100
        assert entity.char_end == 112

    def test_a_single_trailing_period_moves_the_offset_by_one(self):
        source = "Tamilnadu."
        records = _records_from_text(source)

        entity = reconstruct_entities(_predict(records, [0], "ADDRESS"), records)[0]

        assert entity.entity_value == "Tamilnadu"
        assert entity.char_end == len("Tamilnadu")


class TestOrphanedBracketsAreRemoved:
    """Row 17."""

    def test_enclosing_brackets_are_stripped_from_both_ends(self):
        records = _records_from_text("(CSE)")

        entity = reconstruct_entities(_predict(records, [0], "DEGREE"), records)[0]

        assert entity.entity_value == "CSE"
        assert "(" not in entity.entity_value and ")" not in entity.entity_value
        assert entity.char_start == 1
        assert entity.char_end == 4

    def test_an_unmatched_trailing_bracket_is_stripped(self):
        """The development tenant stored `O Konni, Pathanamthitta (Dist),` — the closing
        bracket and comma are outside, the opening bracket is interior."""
        source = "O Konni, Pathanamthitta (Dist),"
        records = _records_from_text(source)

        entity = reconstruct_entities(_predict(records, [0, 1, 2, 3], "ADDRESS"), records)[0]

        assert entity.entity_value == "O Konni, Pathanamthitta (Dist"
        assert entity.char_end == source.index("),")


class TestInteriorPunctuationSurvives:
    """Row 18."""

    def test_only_the_outermost_punctuation_is_removed(self):
        source = "Uniqlo Co., Ltd."
        records = _records_from_text(source)

        entity = reconstruct_entities(_predict(records, [0, 1, 2], "COMPANY"), records)[0]

        assert entity.entity_value == "Uniqlo Co., Ltd"
        assert "Co.," in entity.entity_value

    def test_an_email_keeps_its_dots(self):
        records = _records_from_text("arjun.jayan@gmail.com")

        entity = reconstruct_entities(_predict(records, [0], "EMAIL"), records)[0]

        assert entity.entity_value == "arjun.jayan@gmail.com"

    def test_an_interior_hyphen_and_slash_survive(self):
        records = _records_from_text("Diploma in UI/UX")

        entity = reconstruct_entities(_predict(records, [0, 1, 2], "DEGREE"), records)[0]

        assert entity.entity_value == "Diploma in UI/UX"


class TestOffsetsStillDelimitTheStoredValue:
    """Row 19 — the property that makes citations resolvable."""

    @pytest.mark.parametrize("source,indices,entity_type", [
        ("Centizen Inc.,", [0], "COMPANY"),
        ("(CSE)", [0], "DEGREE"),
        ("Uniqlo Co., Ltd.", [0, 1, 2], "COMPANY"),
        ("Having two and a half years of experience", [1, 4, 5], "YEARS_OF_EXP"),
        ("Government Higher Secondary School,", [0, 1, 2, 3], "INSTITUTION"),
        ("B.Sc., Information Technology", [0, 1, 2], "DEGREE"),
    ])
    def test_slicing_the_source_reproduces_the_value(self, source, indices, entity_type):
        records = _records_from_text(source)
        predictions = _predict(records, indices, entity_type)

        entity = reconstruct_entities(predictions, records)[0]

        assert entity.char_start is not None and entity.char_end is not None
        assert source[entity.char_start:entity.char_end] == entity.entity_value

    def test_offsets_are_none_when_the_span_carries_none(self):
        predictions = [
            {"token": "Acme", "label": "B-COMPANY", "confidence": 0.9},
            {"token": "Corp", "label": "I-COMPANY", "confidence": 0.9},
        ]

        entity = reconstruct_entities(predictions)[0]

        assert entity.char_start is None
        assert entity.char_end is None
        assert entity.entity_value == "Acme Corp"
