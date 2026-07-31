import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.extraction_service.worker import _align_predictions_with_offsets, _tokenize_span


class TestTokenizeSpanMatchesOldSplitSemantics:
    """verification.md task 4.3: the new offset-carrying tokenizer must produce the
    same token list as the old `doc_text.split()` over the joined span text."""

    def test_multi_span_document_token_list_is_identical_to_split(self):
        spans = [
            ("John works at", 1, 0),
            ("Acme Corp in New York.", 1, 15),
        ]
        old_style_tokens = " ".join(s[0] for s in spans).split()

        token_records = []
        for span_text, page_number, char_start in spans:
            token_records.extend(_tokenize_span(span_text, page_number, char_start))
        new_tokens = [t["token"] for t in token_records]

        assert new_tokens == old_style_tokens

    def test_tokens_carry_page_and_offset_metadata(self):
        records = _tokenize_span("Computer Science Engineering", 2, 100)
        assert [r["token"] for r in records] == ["Computer", "Science", "Engineering"]
        assert records[0]["page_number"] == 2
        assert records[0]["char_start"] == 100
        assert records[0]["char_end"] == 108
        assert records[2]["char_start"] == 117
        assert records[2]["char_end"] == 128

    def test_span_with_no_offset_yields_none(self):
        records = _tokenize_span("Kerala", None, None)
        assert records[0]["char_start"] is None
        assert records[0]["char_end"] is None


class TestAlignPredictionsWithOffsets:
    def test_aligned_prediction_receives_token_offsets(self):
        token_records = [
            {"token": "Computer", "page_number": 2, "char_start": 100, "char_end": 108},
            {"token": "Science", "page_number": 2, "char_start": 109, "char_end": 116},
        ]
        predictions = [
            {"token": "Computer", "label": "B-ORG", "confidence": 0.9},
            {"token": "Science", "label": "I-ORG", "confidence": 0.8},
        ]
        aligned = _align_predictions_with_offsets(predictions, token_records)
        assert aligned[0]["char_start"] == 100
        assert aligned[1]["char_end"] == 116

    def test_unmatched_prediction_gets_none_offsets(self):
        token_records = [{"token": "Kerala", "page_number": 1, "char_start": 0, "char_end": 6}]
        predictions = [{"token": "Ghost", "label": "B-PER", "confidence": 0.5}]
        aligned = _align_predictions_with_offsets(predictions, token_records)
        assert aligned[0]["page_number"] is None
        assert aligned[0]["char_start"] is None
        assert aligned[0]["char_end"] is None
