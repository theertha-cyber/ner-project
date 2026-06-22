"""Unit tests for _compute_bio_tags in spans.py."""
import pytest
from src.annotation_service.api.v1.spans import _compute_bio_tags


def test_single_token_b_only():
    """Single-token span produces only a B- tag."""
    result = _compute_bio_tags("Acme Corp", 0, 4, "ORG")
    assert result == ["B-ORG"]


def test_two_token_b_and_i():
    """Two-token span produces B- then I-."""
    result = _compute_bio_tags("John Smith works here", 0, 10, "PER")
    assert result == ["B-PER", "I-PER"]


def test_non_zero_char_start():
    """Span not starting at position 0 computes correct absolute offsets."""
    # "Smith" is at char_start=5, char_end=10 in "John Smith works here"
    result = _compute_bio_tags("John Smith works here", 5, 10, "PER")
    assert result == ["B-PER"]


def test_multi_token_span():
    """Span covering three tokens produces B + I + I."""
    result = _compute_bio_tags("New York City is great", 0, 13, "LOC")
    assert result == ["B-LOC", "I-LOC", "I-LOC"]


def test_span_in_middle():
    """Span in the middle of a sentence only tags relevant tokens."""
    # "Smith works" → char_start=5, char_end=16 in "John Smith works here"
    result = _compute_bio_tags("John Smith works here", 5, 16, "ORG")
    assert result == ["B-ORG", "I-ORG"]
