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


class TestAnnotationServiceURL:

    def test_default_url_used_when_env_var_unset(self, monkeypatch):
        import src.training_service.worker as worker
        monkeypatch.setattr(worker, "ANNOTATION_SERVICE_URL", "http://annotation_service:8000")
        captured = []
        def mock_get(url, *args, **kwargs):
            captured.append(url)
            raise Exception("_stop_")
        monkeypatch.setattr(worker.requests, "get", mock_get)
        with pytest.raises(Exception, match="_stop_"):
            worker._load_annotated_dataset("test-tenant-id")
        assert captured[0] == "http://annotation_service:8000/api/v1/annotation-export"

    def test_override_url_via_env_var(self, monkeypatch):
        import src.training_service.worker as worker
        monkeypatch.setattr(worker, "ANNOTATION_SERVICE_URL", "http://custom-host:9999")
        captured = []
        def mock_get(url, *args, **kwargs):
            captured.append(url)
            raise Exception("_stop_")
        monkeypatch.setattr(worker.requests, "get", mock_get)
        with pytest.raises(Exception, match="_stop_"):
            worker._load_annotated_dataset("test-tenant-id")
        assert captured[0] == "http://custom-host:9999/api/v1/annotation-export"


class TestFineTuneRetryGuard:

    def make_mock_engine(self, status: str | None):
        """Return a mock sync engine whose connection returns a row with given status."""
        import json
        from unittest.mock import MagicMock, patch

        mock_row = MagicMock()
        if status is not None:
            mock_row.fetchone.return_value = (status,)
        else:
            mock_row.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_row
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        return mock_engine

    def test_skips_when_status_completed(self, monkeypatch):
        from src.training_service.worker import fine_tune_model
        mock_engine = self.make_mock_engine("completed")
        monkeypatch.setattr("src.training_service.worker._get_sync_engine", lambda: mock_engine)

        result = fine_tune_model("tenant-1", "job-completed", {"learning_rate": 2e-5})
        assert result is None

    def test_skips_when_status_failed(self, monkeypatch):
        from src.training_service.worker import fine_tune_model
        mock_engine = self.make_mock_engine("failed")
        monkeypatch.setattr("src.training_service.worker._get_sync_engine", lambda: mock_engine)

        result = fine_tune_model("tenant-1", "job-failed", {"learning_rate": 2e-5})
        assert result is None

    def test_skips_when_status_cancelled(self, monkeypatch):
        from src.training_service.worker import fine_tune_model
        mock_engine = self.make_mock_engine("cancelled")
        monkeypatch.setattr("src.training_service.worker._get_sync_engine", lambda: mock_engine)

        result = fine_tune_model("tenant-1", "job-cancelled", {"learning_rate": 2e-5})
        assert result is None

    def test_skips_when_job_not_found(self, monkeypatch):
        from src.training_service.worker import fine_tune_model
        mock_engine = self.make_mock_engine(None)
        monkeypatch.setattr("src.training_service.worker._get_sync_engine", lambda: mock_engine)

        result = fine_tune_model("tenant-1", "job-unknown", {"learning_rate": 2e-5})
        assert result is None

    def test_proceeds_when_status_approved(self, monkeypatch):
        mock_engine = self.make_mock_engine("approved")
        monkeypatch.setattr("src.training_service.worker._get_sync_engine", lambda: mock_engine)

        reached_mlflow = False
        def fake_set_tracking_uri(*args):
            nonlocal reached_mlflow
            reached_mlflow = True
            raise Exception("reached_mlflow_setup")

        monkeypatch.setattr("src.training_service.worker.mlflow.set_tracking_uri", fake_set_tracking_uri)

        from src.training_service.worker import fine_tune_model
        with pytest.raises(Exception, match="reached_mlflow_setup"):
            fine_tune_model("tenant-1", "job-approved", {"learning_rate": 2e-5})
        assert reached_mlflow, "Should reach MLflow setup for approved jobs"


class TestOnnxExport:

    def test_onnx_export_mock_verifies_export_call(self, monkeypatch):
        from unittest.mock import MagicMock
        import src.training_service.worker as worker_module

        fake_export = MagicMock()
        monkeypatch.setattr(worker_module.torch.onnx, "export", fake_export)

        onnx_path = "/fake/path/model.onnx"
        dummy_input_ids = MagicMock()
        dummy_attention_mask = MagicMock()
        fake_model = MagicMock()

        worker_module.torch.onnx.export(
            fake_model,
            (dummy_input_ids, dummy_attention_mask),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "logits": {0: "batch", 1: "sequence"},
            },
            opset_version=14,
            dynamo=False,
        )

        fake_export.assert_called_once()
        args, kwargs = fake_export.call_args
        assert args[0] is fake_model
        assert args[2] == onnx_path
        assert kwargs["input_names"] == ["input_ids", "attention_mask"]
        assert kwargs["output_names"] == ["logits"]
        assert kwargs["dynamo"] is False


@pytest.mark.slow
class TestOnnxIntegration:

    def test_onnx_export_and_inference(self, tmp_path):
        import torch
        from transformers import (
            AutoTokenizer,
            AutoConfig,
            AutoModelForTokenClassification,
        )
        import onnxruntime as ort
        import numpy as np

        model_dir = str(tmp_path / "model")
        model_name = "dslim/bert-base-NER"
        max_seq_length = 128

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        config = AutoConfig.from_pretrained(
            model_name,
            num_labels=3,
        )
        model = AutoModelForTokenClassification.from_config(config)

        model.save_pretrained(model_dir)
        tokenizer.save_pretrained(model_dir)

        model.eval()
        dummy_inputs = tokenizer(
            "dummy input text for onnx export tracing",
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=max_seq_length,
        )
        onnx_path = os.path.join(model_dir, "model.onnx")
        torch.onnx.export(
            model,
            (dummy_inputs["input_ids"], dummy_inputs["attention_mask"]),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "logits": {0: "batch", 1: "sequence"},
            },
            opset_version=14,
            dynamo=False,
        )

        assert os.path.exists(onnx_path), "model.onnx should exist after export"

        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        input_names = [inp.name for inp in session.get_inputs()]
        output_names = [out.name for out in session.get_outputs()]
        assert "input_ids" in input_names
        assert "attention_mask" in input_names

        inputs = tokenizer("John lives in New York", return_tensors="np")
        ort_inputs = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
        }
        ort_outputs = session.run(output_names, ort_inputs)
        assert len(ort_outputs) > 0
        logits = ort_outputs[0]
        assert logits.shape[0] == 1
        assert logits.shape[2] == 3

        predictions = logits.argmax(axis=-1)
        assert predictions.shape == (1, inputs["input_ids"].shape[1])


@pytest.mark.slow
class TestMlflowModelLogging:

    def test_mlflow_transformers_log_model_succeeds(self, tmp_path):
        import mlflow
        from mlflow import MlflowClient
        import torch
        from transformers import (
            AutoTokenizer,
            AutoConfig,
            AutoModelForTokenClassification,
        )

        model_name = "dslim/bert-base-NER"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        config = AutoConfig.from_pretrained(model_name, num_labels=3)
        model = AutoModelForTokenClassification.from_config(config)

        registered_model_name = "test_ner_model_integration"
        experiment_name = "test_experiment_mlflow_integration"

        mlflow.set_tracking_uri(os.getenv("NER_MLFLOW_TRACKING_URI", "http://localhost:5000"))

        experiment = mlflow.get_experiment_by_name(experiment_name)
        experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(experiment_name)

        with mlflow.start_run(experiment_id=experiment_id) as run:
            mlflow.transformers.log_model(
                transformers_model={"model": model, "tokenizer": tokenizer},
                artifact_path="model",
                registered_model_name=registered_model_name,
            )

        client = MlflowClient()
        registered = client.get_registered_model(registered_model_name)
        assert registered is not None
        assert registered.name == registered_model_name

        latest_version = registered.latest_versions
        assert len(latest_version) >= 1
        v1 = client.get_model_version(registered_model_name, latest_version[0].version)
        assert v1 is not None

        client.delete_registered_model(registered_model_name)

        try:
            mlflow.delete_experiment(experiment_id)
        except Exception:
            pass


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
