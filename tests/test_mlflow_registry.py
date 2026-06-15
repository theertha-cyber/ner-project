import pytest
from datetime import datetime, timezone

from src.training_service.infra.mlflow_registry import (
    STATUS_TO_STAGE,
    STAGE_TO_STATUS,
    _registered_model_name,
    _experiment_name,
    list_model_versions,
    get_active_model,
    promote_model_version,
    demote_model_version,
)


class TestNamingConventions:
    def test_registered_model_name(self):
        assert _registered_model_name("abc-123") == "tenant_abc-123_ner_model"
        assert _registered_model_name("tenant-x") == "tenant_tenant-x_ner_model"

    def test_experiment_name(self):
        assert _experiment_name("abc-123") == "tenant_abc-123"


class TestStatusToStageMapping:
    def test_all_statuses_mapped(self):
        assert STATUS_TO_STAGE["completed"] == "Staging"
        assert STATUS_TO_STAGE["promoted"] == "Production"
        assert STATUS_TO_STAGE["archived"] == "Archived"

    def test_all_stages_map_back(self):
        assert STAGE_TO_STATUS["Staging"] == "completed"
        assert STAGE_TO_STATUS["Production"] == "promoted"
        assert STAGE_TO_STATUS["Archived"] == "archived"

    def test_roundtrip(self):
        for status, stage in STATUS_TO_STAGE.items():
            assert STAGE_TO_STATUS[stage] == status


class TestListModelVersions:
    def test_list_returns_empty_when_no_registered_model(self, monkeypatch):
        from mlflow.exceptions import RestException

        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise RestException({"message": "not found", "error_code": "RESOURCE_DOES_NOT_EXIST"})

                def get_run(self, run_id):
                    pass

            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)
        result, warning = list_model_versions("tenant-x")
        assert result == []
        assert warning is None

    def test_list_returns_cached_on_exception(self, monkeypatch):
        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise Exception("MLflow unreachable")

                def get_run(self, run_id):
                    pass

            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)

        def mock_read_cache(*args, **kwargs):
            return [{"version_number": 1, "status": "completed"}]

        monkeypatch.setattr("src.training_service.infra.mlflow_registry._read_cache_model_versions", mock_read_cache)

        result, warning = list_model_versions("tenant-x")
        assert len(result) == 1
        assert warning == "mlflow-unavailable"


class TestPromoteModelVersion:
    def test_promote_returns_none_when_no_registered_model(self, monkeypatch):
        from mlflow.exceptions import RestException

        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise RestException({"message": "not found", "error_code": "RESOURCE_DOES_NOT_EXIST"})

            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)
        result = promote_model_version("tenant-x", 1)
        assert result is None


class TestDemoteModelVersion:
    def test_demote_returns_none_when_no_registered_model(self, monkeypatch):
        from mlflow.exceptions import RestException

        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise RestException({"message": "not found", "error_code": "RESOURCE_DOES_NOT_EXIST"})

            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)
        result = demote_model_version("tenant-x", 1)
        assert result is None


class TestGetActiveModel:
    def test_get_active_returns_cached_on_exception(self, monkeypatch):
        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise Exception("MLflow unreachable")

                def get_run(self, run_id):
                    pass

            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)

        def mock_read_cache(*args, **kwargs):
            return {"version_number": 2, "status": "promoted", "mlflow_run_id": "run-1"}

        monkeypatch.setattr("src.training_service.infra.mlflow_registry._read_cache_active_model", mock_read_cache)

        result, warning = get_active_model("tenant-x")
        assert result is not None
        assert result["version_number"] == 2
        assert warning == "mlflow-unavailable"
