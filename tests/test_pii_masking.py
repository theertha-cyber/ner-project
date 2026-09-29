"""Safe-copy generation: local detection, placeholder substitution, and offset translation.

Covers the `automated-annotation-pii-masking` change's Safe-Copy Generation, Placeholder
Stability, and Fail-Closed requirements. Pure functions and a stub local-model client only: no
database, no network — the real `ModelServingClient` is the one thing these tests must not reach.
"""

import pytest

from src.annotation_service.services.pii_masking import (
    LocalDetectionUnavailable,
    StubLocalModelClient,
    detect_local_only_spans,
    detect_pattern_spans,
    find_uncovered_local_only_type,
    mask_document,
    translate_offset,
)

OPEN_TYPE = {"name": "organization", "sensitivity": "open"}
PATTERN_TYPE = {
    "name": "ssn",
    "sensitivity": "pattern",
    "validation_rule": r"\d{3}-\d{2}-\d{4}",
}
LOCAL_ONLY_MAPPED = {
    "name": "child_name",
    "sensitivity": "local_only",
    "base_label_mapping": {"PER": ["child_name"]},
}
LOCAL_ONLY_UNMAPPED = {
    "name": "case_notes",
    "sensitivity": "local_only",
    "base_label_mapping": {},
}


class TestDetectPatternSpans:
    def test_finds_a_matching_span(self):
        text = "SSN: 123-45-6789 on file"
        spans = detect_pattern_spans(text, [PATTERN_TYPE])
        assert len(spans) == 1
        assert spans[0]["entity_type"] == "ssn"
        assert spans[0]["text"] == "123-45-6789"
        assert spans[0]["source"] == "pattern"
        assert text[spans[0]["char_start"]:spans[0]["char_end"]] == "123-45-6789"

    def test_ignores_open_and_local_only_types(self):
        text = "Acme Corp hired John."
        spans = detect_pattern_spans(text, [OPEN_TYPE, LOCAL_ONLY_MAPPED])
        assert spans == []

    def test_no_match_returns_empty(self):
        assert detect_pattern_spans("no ssn here", [PATTERN_TYPE]) == []

    def test_broken_regex_raises_rather_than_matching_nothing(self):
        broken = {"name": "ssn", "sensitivity": "pattern", "validation_rule": "("}
        with pytest.raises(LocalDetectionUnavailable):
            detect_pattern_spans("some text", [broken])


class TestDetectLocalOnlySpans:
    def test_maps_a_base_label_prediction_to_the_tenant_type(self):
        text = "Jimmy Smith was placed with the Doe family"
        client = StubLocalModelClient(
            predictions=[
                {"token": "Jimmy", "label": "B-PER", "confidence": 0.9, "word_index": 0},
                {"token": "Smith", "label": "I-PER", "confidence": 0.9, "word_index": 1},
            ]
        )
        spans = detect_local_only_spans(text, [LOCAL_ONLY_MAPPED], client, "tenant-1")
        assert len(spans) == 1
        assert spans[0]["entity_type"] == "child_name"
        assert spans[0]["text"] == "Jimmy Smith"
        assert spans[0]["source"] == "local_model"
        assert client.call_count == 1
        assert client.calls[0][0] == "tenant-1"

    def test_no_local_only_types_never_calls_the_client(self):
        client = StubLocalModelClient(predictions=[{"token": "x", "label": "B-PER"}])
        spans = detect_local_only_spans("some text", [OPEN_TYPE], client, "tenant-1")
        assert spans == []
        assert client.call_count == 0

    def test_unrecognized_label_produces_no_span(self):
        client = StubLocalModelClient(
            predictions=[{"token": "Acme", "label": "B-ORG", "confidence": 0.9, "word_index": 0}]
        )
        spans = detect_local_only_spans("Acme did it", [LOCAL_ONLY_MAPPED], client, "tenant-1")
        assert spans == []

    def test_client_failure_propagates_rather_than_returning_empty(self):
        client = StubLocalModelClient(fail=True)
        with pytest.raises(LocalDetectionUnavailable):
            detect_local_only_spans("Jimmy Smith", [LOCAL_ONLY_MAPPED], client, "tenant-1")


class TestFindUncoveredLocalOnlyType:
    def test_returns_none_when_every_local_only_type_is_mapped(self):
        assert find_uncovered_local_only_type([OPEN_TYPE, LOCAL_ONLY_MAPPED]) is None

    def test_returns_the_unmapped_type_name(self):
        assert find_uncovered_local_only_type([LOCAL_ONLY_UNMAPPED]) == "case_notes"

    def test_open_and_pattern_types_are_never_flagged(self):
        assert find_uncovered_local_only_type([OPEN_TYPE, PATTERN_TYPE]) is None


class TestMaskDocument:
    def test_no_sensitive_types_leaves_the_copy_identical(self):
        text = "Acme Corp hired John Doe."
        client = StubLocalModelClient()
        result = mask_document(text, [OPEN_TYPE], client, "tenant-1")
        assert result.masked_text == text
        assert result.local_spans == []

    def test_a_pattern_match_is_replaced_with_a_placeholder(self):
        text = "SSN: 123-45-6789 on file"
        client = StubLocalModelClient()
        result = mask_document(text, [PATTERN_TYPE], client, "tenant-1")
        assert "123-45-6789" not in result.masked_text
        assert "SSN_1" in result.masked_text or "⟦SSN_1⟧" in result.masked_text

    def test_repeated_mentions_share_one_placeholder(self):
        text = "Jimmy Smith called. Later, Jimmy Smith called again."
        client = StubLocalModelClient(
            predictions=[
                {"token": "Jimmy", "label": "B-PER", "confidence": 0.9, "word_index": 0},
                {"token": "Smith", "label": "I-PER", "confidence": 0.9, "word_index": 1},
                {"token": "Jimmy", "label": "B-PER", "confidence": 0.9, "word_index": 4},
                {"token": "Smith", "label": "I-PER", "confidence": 0.9, "word_index": 5},
            ]
        )
        result = mask_document(text, [LOCAL_ONLY_MAPPED], client, "tenant-1")
        # Both occurrences of "Jimmy Smith" collapse to the identical placeholder token.
        first_ph = result.masked_text.split("called")[0].strip()
        second_ph_region = result.masked_text.split("Later,")[1].split("called")[0].strip()
        assert first_ph == second_ph_region

    def test_distinct_values_get_distinct_placeholders(self):
        text = "Jimmy Smith and Maria Lopez were both present."
        client = StubLocalModelClient(
            predictions=[
                {"token": "Jimmy", "label": "B-PER", "confidence": 0.9, "word_index": 0},
                {"token": "Smith", "label": "I-PER", "confidence": 0.9, "word_index": 1},
                {"token": "Maria", "label": "B-PER", "confidence": 0.9, "word_index": 3},
                {"token": "Lopez", "label": "I-PER", "confidence": 0.9, "word_index": 4},
            ]
        )
        result = mask_document(text, [LOCAL_ONLY_MAPPED], client, "tenant-1")
        assert "CHILD_NAME_1" in result.masked_text
        assert "CHILD_NAME_2" in result.masked_text

    def test_local_detection_failure_propagates(self):
        client = StubLocalModelClient(fail=True)
        with pytest.raises(LocalDetectionUnavailable):
            mask_document("Jimmy Smith", [LOCAL_ONLY_MAPPED], client, "tenant-1")


class TestTranslateOffset:
    def test_translates_a_location_after_a_masked_span(self):
        text = "Jimmy Smith is a resident of Example House"
        client = StubLocalModelClient(
            predictions=[
                {"token": "Jimmy", "label": "B-PER", "confidence": 0.9, "word_index": 0},
                {"token": "Smith", "label": "I-PER", "confidence": 0.9, "word_index": 1},
            ]
        )
        result = mask_document(text, [LOCAL_ONLY_MAPPED], client, "tenant-1")

        masked_pos = result.masked_text.index("Example House")
        translated = translate_offset(
            masked_pos, masked_pos + len("Example House"), result.segments
        )
        assert translated is not None
        orig_start, orig_end = translated
        assert text[orig_start:orig_end] == "Example House"

    def test_a_range_inside_a_placeholder_does_not_translate(self):
        text = "Jimmy Smith is here"
        client = StubLocalModelClient(
            predictions=[
                {"token": "Jimmy", "label": "B-PER", "confidence": 0.9, "word_index": 0},
                {"token": "Smith", "label": "I-PER", "confidence": 0.9, "word_index": 1},
            ]
        )
        result = mask_document(text, [LOCAL_ONLY_MAPPED], client, "tenant-1")
        assert translate_offset(0, 3, result.segments) is None

    def test_identity_translation_when_nothing_is_masked(self):
        text = "Acme Corp hired John Doe."
        result = mask_document(text, [OPEN_TYPE], StubLocalModelClient(), "tenant-1")
        translated = translate_offset(0, len("Acme Corp"), result.segments)
        assert translated == (0, len("Acme Corp"))
