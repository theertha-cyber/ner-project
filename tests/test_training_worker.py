import os
import json
import pytest

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_TRAINING_DEVICE", "cpu")

from src.shared.config import settings
from src.training_service.worker import (
    _extract_label_set,
    TrainingDataError,
)


class TestExtractLabelSet:

    def test_extracts_unique_labels(self):
        records = [
            {"tokens": ["John", "lives", "in", "NYC"], "tags": ["B-PER", "O", "O", "B-LOC"]},
            {"tokens": ["Alice", "works", "at", "Acme"], "tags": ["B-PER", "O", "O", "B-ORG"]},
        ]
        labels = _extract_label_set(records)
        assert labels == ["O", "B-LOC", "B-ORG", "B-PER"]

    def test_all_o_returns_just_o(self):
        records = [
            {"tokens": ["hello", "world"], "tags": ["O", "O"]},
        ]
        labels = _extract_label_set(records)
        assert labels == ["O"]

    def test_empty_records(self):
        labels = _extract_label_set([])
        assert labels == ["O"]


class TestLoadAnnotatedDataset:

    def test_empty_response_raises_error(self, monkeypatch):
        def mock_get(*args, **kwargs):
            class MockResponse:
                status_code = 200
                text = ""
                def raise_for_status(self):
                    pass
            return MockResponse()
        monkeypatch.setattr("src.training_service.worker.requests.get", mock_get)
        from src.training_service.worker import _load_annotated_dataset
        with pytest.raises(TrainingDataError, match="No annotated data found"):
            _load_annotated_dataset("test-tenant-id")

    def test_parses_jsonl_lines(self, monkeypatch):
        records_data = [
            {"tokens": ["hello", "world"], "tags": ["O", "O"]},
            {"tokens": ["John", "Smith"], "tags": ["B-PER", "I-PER"]},
        ]
        jsonl = "\n".join(json.dumps(r) for r in records_data)

        def mock_get(*args, **kwargs):
            class MockResponse:
                status_code = 200
                text = jsonl
                def raise_for_status(self):
                    pass
            return MockResponse()
        monkeypatch.setattr("src.training_service.worker.requests.get", mock_get)
        from src.training_service.worker import _load_annotated_dataset
        result = _load_annotated_dataset("test-tenant-id")
        assert len(result) == 2
        assert result[0]["tokens"] == ["hello", "world"]
        assert result[1]["tags"] == ["B-PER", "I-PER"]


@pytest.mark.slow
class TestTokenizeAlignment:

    def test_subword_alignment(self):
        from src.training_service.worker import _extract_label_set, tokenize_and_align_labels
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("dslim/bert-base-NER")
        records = [{"tokens": ["John", "smith"], "tags": ["B-PER", "I-PER"]}]
        label_list = _extract_label_set(records)
        label2id = {lbl: i for i, lbl in enumerate(label_list)}
        # tokenize_and_align_labels expects batched format (dict of lists)
        batch = {
            "tokens": [r["tokens"] for r in records],
            "tags": [r["tags"] for r in records],
        }
        result = tokenize_and_align_labels(batch, tok, label2id, 128)
        assert "labels" in result
        assert len(result["labels"]) == 1
        assert result["labels"][0] != -100


class TestLabelMapping:

    def test_label2id_mapping(self):
        from src.training_service.worker import _extract_label_set
        records = [
            {"tokens": ["a", "b"], "tags": ["B-PER", "I-PER"]},
            {"tokens": ["c", "d"], "tags": ["B-LOC", "O"]},
        ]
        label_list = _extract_label_set(records)
        label2id = {lbl: i for i, lbl in enumerate(label_list)}
        assert label2id["O"] == 0
        assert label2id["B-PER"] >= 1
        assert label2id["B-LOC"] >= 1
        assert label2id["I-PER"] >= 1
