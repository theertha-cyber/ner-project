"""Grounding: offsets come from the text, never from the model.

design.md Decisions 2 and 4. The model says what it saw; this layer decides where it is, by
exact case-insensitive match, and drops whatever will not match. These are the tests that would
fail first if someone added a fuzzy fallback to "rescue" near-misses — which is precisely the
hallucination risk verification.md § 2 row 2 names.

Covers verification.md rows 6-10. Pure functions only: no database, no network.
"""

import pytest

from src.annotation_service.services.llm_prelabel import (
    LLM_SUGGESTION_CONFIDENCE,
    ground_entities,
    ground_quote,
    parse_llm_response,
)

ACTIVE_TYPES = ["person_name", "institute", "organization", "years_experience"]


class TestGroundingSucceeds:
    """verification.md row 7."""

    def test_quote_grounds_to_single_location(self):
        document_text = "John Doe joined as Senior Engineer"
        result = ground_entities(
            document_text,
            [{"entity_type": "person_name", "quote": "John Doe"}],
            ACTIVE_TYPES,
        )

        assert len(result.spans) == 1
        span = result.spans[0]
        assert span["entity_type"] == "person_name"
        assert span["char_start"] == 0
        assert span["char_end"] == 8
        assert span["text"] == "John Doe"
        assert span["source"] == "llm"
        assert span["confidence"] == LLM_SUGGESTION_CONFIDENCE
        assert document_text[span["char_start"] : span["char_end"]] == span["text"]

    def test_match_is_case_insensitive_but_the_stored_text_is_the_document_s(self):
        document_text = "JOHN DOE joined as Senior Engineer"
        result = ground_entities(
            document_text, [{"entity_type": "person_name", "quote": "John Doe"}], ACTIVE_TYPES
        )
        assert result.spans[0]["text"] == "JOHN DOE"


class TestGroundingFailureDrops:
    """verification.md row 8."""

    def test_unmatched_quote_is_dropped(self):
        document_text = "John Doe joined as Senior Engineer"
        result = ground_entities(
            document_text,
            [{"entity_type": "person_name", "quote": "Jane Smith"}],
            ACTIVE_TYPES,
        )

        assert result.spans == []
        assert result.returned == 1
        assert result.grounded == 0
        assert result.ungrounded == 1

    @pytest.mark.parametrize(
        "quote",
        [
            "John  Doe",  # collapsed whitespace would rescue this
            "JohnDoe",  # removed whitespace would rescue this
            "John Dow",  # an edit-distance fallback would rescue this
            "Jon Doe",  # so would a phonetic one
            "Doe, John",  # so would a reordering one
        ],
    )
    def test_near_misses_are_dropped_rather_than_rescued(self, quote):
        """No normalisation, no fuzzy matching, no nearest-match fallback.

        A wrong offset is worse than a missing suggestion: it corrupts a training label
        silently, or points a reviewer at text that is not what the span claims it is."""
        assert ground_quote("John Doe joined as Senior Engineer", quote, []) is None

    def test_a_truncated_quote_grounds_because_it_is_an_exact_substring(self):
        """Not a near-miss, despite looking like one.

        "John Do" is literally present in "John Doe", so exact substring matching finds it and
        the resulting span points at text that really is there — which is the whole guarantee.
        A short span is a reviewer's problem to fix at the approval gate; it is not the kind of
        wrong the drop rule exists to prevent."""
        assert ground_quote("John Doe joined as Senior Engineer", "John Do", []) == (0, 7)


class TestDuplicateQuotes:
    """verification.md row 9 — the rule signed off in design.md as task 1.3."""

    def test_duplicate_quote_takes_first_occurrence(self):
        document_text = "Acme Corp hired John. Acme Corp also promoted John."
        result = ground_entities(
            document_text,
            [{"entity_type": "organization", "quote": "Acme Corp"}],
            ACTIVE_TYPES,
        )

        assert len(result.spans) == 1
        assert result.spans[0]["char_start"] == 0
        assert result.spans[0]["char_end"] == 9

    def test_second_return_of_the_same_quote_grounds_to_the_next_free_occurrence(self):
        """"first occurrence not already claimed" — an independently returned second mention
        is not lost to the first one having taken position 0."""
        document_text = "Acme Corp hired John. Acme Corp also promoted John."
        result = ground_entities(
            document_text,
            [
                {"entity_type": "organization", "quote": "Acme Corp"},
                {"entity_type": "organization", "quote": "Acme Corp"},
            ],
            ACTIVE_TYPES,
        )

        assert [span["char_start"] for span in result.spans] == [0, 22]

    def test_a_third_return_with_only_two_occurrences_is_dropped(self):
        document_text = "Acme Corp hired John. Acme Corp also promoted John."
        result = ground_entities(
            document_text,
            [{"entity_type": "organization", "quote": "Acme Corp"}] * 3,
            ACTIVE_TYPES,
        )

        assert len(result.spans) == 2
        assert result.ungrounded == 1

    def test_an_overlapping_span_does_not_claim_a_position_twice(self):
        document_text = "Apple Inc is based in Cupertino"
        result = ground_entities(
            document_text,
            [
                {"entity_type": "organization", "quote": "Apple Inc"},
                {"entity_type": "organization", "quote": "Apple"},
            ],
            ACTIVE_TYPES,
        )

        assert len(result.spans) == 1
        assert result.spans[0]["text"] == "Apple Inc"


class TestEntityTypeConstraint:
    """verification.md row 10."""

    def test_unconfigured_entity_type_is_dropped(self):
        document_text = "John Doe joined as Senior Engineer"
        result = ground_entities(
            document_text,
            [
                {"entity_type": "person_name", "quote": "John Doe"},
                {"entity_type": "job_title", "quote": "Senior Engineer"},
            ],
            ["institute", "person_name"],
        )

        stored_types = {span["entity_type"] for span in result.spans}
        assert stored_types == {"person_name"}
        assert "job_title" not in stored_types
        assert result.unconfigured_type == 1

    def test_type_matching_is_case_insensitive_and_stores_the_tenant_s_spelling(self):
        result = ground_entities(
            "John Doe joined",
            [{"entity_type": "PERSON_NAME", "quote": "John Doe"}],
            ["person_name"],
        )
        assert result.spans[0]["entity_type"] == "person_name"


class TestExtractiveOnly:
    """verification.md row 6."""

    def test_non_extractive_answer_is_not_stored(self):
        """The failure mode the extractive-only contract exists to prevent.

        The document states a date range; a QA pair on `years_experience` invites the answer
        "5 years". The model computes it, the string is nowhere in the text, grounding drops
        it — no span, rather than a span pointing at whatever looked closest."""
        document_text = "Employment history: 2019-2024 at Acme Corp."
        result = ground_entities(
            document_text,
            [{"entity_type": "years_experience", "quote": "5 years"}],
            ACTIVE_TYPES,
        )

        assert result.spans == []
        assert all(span["text"] != "5 years" for span in result.spans)
        assert result.ungrounded == 1

    def test_a_verbatim_quote_from_the_same_document_still_grounds(self):
        """The rule drops what was computed, not everything about the document."""
        document_text = "Employment history: 2019-2024 at Acme Corp."
        result = ground_entities(
            document_text,
            [{"entity_type": "years_experience", "quote": "2019-2024"}],
            ACTIVE_TYPES,
        )
        assert result.spans[0]["text"] == "2019-2024"


class TestOffsetsNeverComeFromTheModel:
    """verification.md § 2 risk 1 — the parser is the enforcement point."""

    @pytest.mark.parametrize(
        "offset_field", ["char_start", "char_end", "start", "end", "offset", "index"]
    )
    def test_offset_fields_in_the_response_are_discarded(self, offset_field):
        parsed = parse_llm_response(
            {"entities": [{"entity_type": "person_name", "quote": "John Doe", offset_field: 999}]}
        )
        assert parsed == [{"entity_type": "person_name", "quote": "John Doe"}]

    def test_a_model_supplied_offset_cannot_reach_a_stored_span(self):
        document_text = "John Doe joined as Senior Engineer"
        parsed = parse_llm_response(
            {
                "entities": [
                    {"entity_type": "person_name", "quote": "John Doe", "char_start": 999}
                ]
            }
        )
        result = ground_entities(document_text, parsed, ACTIVE_TYPES)
        assert result.spans[0]["char_start"] == 0

    @pytest.mark.parametrize(
        "response",
        [
            {"entities": "not a list"},
            {"entities": [{"entity_type": "person_name"}]},
            {"entities": [{"quote": "John Doe"}]},
            {"entities": [{"entity_type": "", "quote": "John Doe"}]},
            {"entities": [None, 7, "text"]},
            {},
            "not json at all",
        ],
    )
    def test_malformed_responses_yield_no_entities_rather_than_raising(self, response):
        assert parse_llm_response(response) == []

    def test_a_bare_list_response_is_accepted(self):
        """Some models drop the envelope; that is not a reason to lose the document's work."""
        assert parse_llm_response([{"entity_type": "person_name", "quote": "John Doe"}]) == [
            {"entity_type": "person_name", "quote": "John Doe"}
        ]

    def test_one_malformed_element_does_not_discard_the_valid_ones(self):
        parsed = parse_llm_response(
            {
                "entities": [
                    {"entity_type": "person_name", "quote": "John Doe"},
                    {"entity_type": 7, "quote": "John Doe"},
                ]
            }
        )
        assert parsed == [{"entity_type": "person_name", "quote": "John Doe"}]


class TestDropRateIsObservable:
    """design.md Risks — a high grounding drop rate must be a number, not an absence."""

    def test_counts_cover_returned_grounded_and_both_drop_reasons(self):
        result = ground_entities(
            "John Doe joined as Senior Engineer",
            [
                {"entity_type": "person_name", "quote": "John Doe"},
                {"entity_type": "person_name", "quote": "Jane Smith"},
                {"entity_type": "job_title", "quote": "Senior Engineer"},
            ],
            ["person_name"],
        )

        assert result.counts() == {
            "returned": 3,
            "grounded": 1,
            "ungrounded": 1,
            "unconfigured_type": 1,
        }
