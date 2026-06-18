"""Comprehensive end-to-end verification of the MLflow integration.

Preconditions:
- MLflow Tracking Server running on NER_MLFLOW_TRACKING_URI (default: http://localhost:5000)
- PostgreSQL DB running on NER_DATABASE_URL_SYNC (default: postgresql://ner:ner@localhost:5432/ner_dev)
- NER_MLFLOW_INTEGRATION_TESTS=1 must be set to run

This script exercises every acceptance criterion from the mlflow-integration
change specs: mlflow-infrastructure, training-worker, model-registry.
"""
import os
import uuid
import json

import pytest
from mlflow.tracking import MlflowClient
import mlflow
import requests
import sqlalchemy as sa

os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:5432/ner_dev")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("NER_MLFLOW_INTEGRATION_TESTS"),
        reason="Set NER_MLFLOW_INTEGRATION_TESTS=1 to run MLflow verification tests",
    ),
    pytest.mark.verification,
    pytest.mark.integration,
]

from src.shared.config import settings
from src.training_service.infra.mlflow_registry import (
    list_model_versions,
    get_active_model,
    promote_model_version,
    demote_model_version,
    _registered_model_name,
    _experiment_name,
    STATUS_TO_STAGE,
    STAGE_TO_STATUS,
    _read_cache_model_versions,
    _read_cache_active_model,
    _schema,
    _get_sync_engine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mlflow_client():
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


@pytest.fixture
def tenant_id():
    return f"verification-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def registered_model_name(tenant_id):
    return _registered_model_name(tenant_id)


@pytest.fixture
def experiment_name(tenant_id):
    return _experiment_name(tenant_id)


@pytest.fixture(autouse=True)
def db_schema(tenant_id):
    engine = sa.create_engine(settings.database_url_sync)
    schema = _schema(tenant_id)
    with engine.begin() as conn:
        conn.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(sa.text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.model_versions (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                version_number INTEGER NOT NULL,
                training_job_id VARCHAR,
                status VARCHAR(20) NOT NULL DEFAULT 'training',
                metrics JSONB,
                artifact_path TEXT,
                mlflow_run_id VARCHAR,
                mlflow_run_url VARCHAR,
                promoted_at TIMESTAMPTZ,
                archived_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
    yield
    with engine.begin() as conn:
        conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    engine.dispose()


@pytest.fixture(autouse=True)
def cleanup(mlflow_client, registered_model_name, experiment_name):
    yield
    try:
        mlflow_client.delete_registered_model(registered_model_name)
    except Exception:
        pass
    try:
        exp = mlflow_client.get_experiment_by_name(experiment_name)
        if exp:
            mlflow_client.delete_experiment(exp.experiment_id)
    except Exception:
        pass


def _create_run(mlflow_client, experiment_name, tags=None, params=None):
    exp = mlflow_client.get_experiment_by_name(experiment_name)
    exp_id = exp.experiment_id if exp else mlflow_client.create_experiment(experiment_name)
    run = mlflow_client.create_run(exp_id, tags=tags or {})
    if params:
        for k, v in params.items():
            mlflow_client.log_param(run.info.run_id, k, v)
    return run, exp_id


def _complete_run(mlflow_client, run, metrics=None):
    if metrics:
        for k, v in metrics.items():
            mlflow_client.log_metric(run.info.run_id, k, v)
    mlflow_client.set_terminated(run.info.run_id)
    return run


# ---------------------------------------------------------------------------
# Layer 1: Infrastructure Health
# ---------------------------------------------------------------------------

class TestInfrastructureHealth:
    def test_server_health(self):
        resp = requests.get(f"{settings.mlflow_tracking_uri}/health", timeout=5)
        assert resp.status_code == 200

    def test_create_experiment(self, mlflow_client, experiment_name):
        exp_id = mlflow_client.create_experiment(experiment_name)
        assert exp_id is not None
        exp = mlflow_client.get_experiment(exp_id)
        assert exp.name == experiment_name


# ---------------------------------------------------------------------------
# Layer 2: Experiment & Run Lifecycle
# ---------------------------------------------------------------------------

class TestExperimentLifecycle:
    def test_create_run_with_params_tags(self, mlflow_client, experiment_name, tenant_id):
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(
            exp_id,
            tags={
                "base_model": "dslim/bert-base-NER",
                "tenant_id": tenant_id,
                "training_job_id": "test-job-123",
                "num_labels": "9",
            },
        )
        mlflow_client.log_param(run.info.run_id, "learning_rate", 2e-5)
        mlflow_client.log_param(run.info.run_id, "num_epochs", 3)
        mlflow_client.log_param(run.info.run_id, "batch_size", 8)
        mlflow_client.log_param(run.info.run_id, "max_seq_length", 128)
        mlflow_client.set_terminated(run.info.run_id)

        run_data = mlflow_client.get_run(run.info.run_id)
        assert run_data.data.params["learning_rate"] == "2e-05"
        assert run_data.data.params["num_epochs"] == "3"
        assert run_data.data.params["batch_size"] == "8"
        assert run_data.data.params["max_seq_length"] == "128"
        assert run_data.data.tags["base_model"] == "dslim/bert-base-NER"
        assert run_data.data.tags["tenant_id"] == tenant_id
        assert run_data.data.tags["training_job_id"] == "test-job-123"
        assert run_data.data.tags["num_labels"] == "9"

    def test_log_metrics_per_step(self, mlflow_client, experiment_name):
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.85, step=0)
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.88, step=1)
        mlflow_client.set_terminated(run.info.run_id)

        run_data = mlflow_client.get_run(run.info.run_id)
        assert float(run_data.data.metrics["eval_f1"]) == 0.88
        metric_history = mlflow_client.get_metric_history(run.info.run_id, "eval_f1")
        assert len(metric_history) == 2
        assert metric_history[0].value == 0.85
        assert metric_history[1].value == 0.88

    def test_run_failure_status(self, mlflow_client, experiment_name):
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.set_tag(run.info.run_id, "error_message", "Out of memory")
        mlflow_client.set_terminated(run.info.run_id, status="FAILED")

        run_data = mlflow_client.get_run(run.info.run_id)
        assert run_data.info.status == "FAILED"
        assert run_data.data.tags.get("error_message") == "Out of memory"


# ---------------------------------------------------------------------------
# Layer 3: Model Registration
# ---------------------------------------------------------------------------

class TestModelRegistration:
    def test_register_model(self, mlflow_client, experiment_name, registered_model_name, tenant_id):
        run, exp_id = _create_run(mlflow_client, experiment_name,
                                   tags={"tenant_id": tenant_id},
                                   params={"training_job_id": "test-job-reg"})
        _complete_run(mlflow_client, run, metrics={"eval_f1": 0.87})

        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv = mlflow_client.create_model_version(
            name=registered_model_name,
            source=model_uri,
            run_id=run.info.run_id,
        )

        registered = mlflow_client.get_registered_model(registered_model_name)
        assert registered.name == registered_model_name
        assert mv.run_id == run.info.run_id
        assert mv.current_stage == "None"


# ---------------------------------------------------------------------------
# Layer 4: Model Registry Proxy
# ---------------------------------------------------------------------------

class TestModelRegistryProxy:
    def test_list_model_versions(self, mlflow_client, experiment_name, registered_model_name, tenant_id):
        run, exp_id = _create_run(mlflow_client, experiment_name,
                                   tags={"tenant_id": tenant_id},
                                   params={"training_job_id": "test-job-list", "artifact_path": "s3://bucket/test"})
        _complete_run(mlflow_client, run, metrics={"eval_f1": 0.87, "eval_precision": 0.85, "eval_recall": 0.89})

        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv = mlflow_client.create_model_version(
            name=registered_model_name,
            source=model_uri,
            run_id=run.info.run_id,
        )
        mlflow_client.transition_model_version_stage(
            name=registered_model_name,
            version=mv.version,
            stage="Staging",
        )

        result, warning = list_model_versions(tenant_id)
        assert len(result) >= 1
        matching = [v for v in result if v["version_number"] == int(mv.version)]
        assert len(matching) >= 1
        assert matching[0]["mlflow_run_id"] == run.info.run_id
        assert "mlflow_run_url" in matching[0]
        assert matching[0]["status"] == "completed"

    def test_promote_model(self, mlflow_client, experiment_name, registered_model_name, tenant_id):
        run, exp_id = _create_run(mlflow_client, experiment_name,
                                   tags={"tenant_id": tenant_id},
                                   params={"training_job_id": "test-job-promote", "artifact_path": "s3://bucket/promote"})
        _complete_run(mlflow_client, run, metrics={"eval_f1": 0.92})

        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv = mlflow_client.create_model_version(
            name=registered_model_name,
            source=model_uri,
            run_id=run.info.run_id,
        )
        mlflow_client.transition_model_version_stage(
            name=registered_model_name,
            version=mv.version,
            stage="Staging",
        )

        result = promote_model_version(tenant_id, int(mv.version))
        assert result is not None
        assert result["status"] == "promoted"

        active, warning = get_active_model(tenant_id)
        assert active is not None
        assert active["version_number"] == int(mv.version)
        assert active["status"] == "promoted"

    def test_promote_archives_previous(self, mlflow_client, experiment_name, registered_model_name, tenant_id):
        run1, exp_id = _create_run(mlflow_client, experiment_name,
                                    tags={"tenant_id": tenant_id},
                                    params={"training_job_id": "test-job-v1", "artifact_path": "s3://bucket/v1"})
        _complete_run(mlflow_client, run1, metrics={"eval_f1": 0.85})

        run2, _ = _create_run(mlflow_client, experiment_name,
                               tags={"tenant_id": tenant_id},
                               params={"training_job_id": "test-job-v2", "artifact_path": "s3://bucket/v2"})
        _complete_run(mlflow_client, run2, metrics={"eval_f1": 0.92})

        model_uri1 = f"runs:/{run1.info.run_id}/model"
        model_uri2 = f"runs:/{run2.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv1 = mlflow_client.create_model_version(name=registered_model_name, source=model_uri1, run_id=run1.info.run_id)
        mv2 = mlflow_client.create_model_version(name=registered_model_name, source=model_uri2, run_id=run2.info.run_id)
        mlflow_client.transition_model_version_stage(name=registered_model_name, version=mv1.version, stage="Production")

        promote_model_version(tenant_id, int(mv2.version))

        v1_details = mlflow_client.get_model_version(registered_model_name, mv1.version)
        assert v1_details.current_stage == "Archived"

        active, _ = get_active_model(tenant_id)
        assert active["version_number"] == int(mv2.version)

    def test_demote_model(self, mlflow_client, experiment_name, registered_model_name, tenant_id):
        run, exp_id = _create_run(mlflow_client, experiment_name,
                                   tags={"tenant_id": tenant_id},
                                   params={"training_job_id": "test-job-demote", "artifact_path": "s3://bucket/demote"})
        _complete_run(mlflow_client, run, metrics={"eval_f1": 0.90})

        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv = mlflow_client.create_model_version(name=registered_model_name, source=model_uri, run_id=run.info.run_id)
        mlflow_client.transition_model_version_stage(name=registered_model_name, version=mv.version, stage="Production")

        result = demote_model_version(tenant_id, int(mv.version))
        assert result is not None
        assert result["status"] == "completed"

        active, warning = get_active_model(tenant_id)
        assert active is None

    def test_list_empty_no_registered_model(self, tenant_id):
        result, warning = list_model_versions(tenant_id)
        assert result == []
        assert warning is None


# ---------------------------------------------------------------------------
# Layer 5: Cache Fallback (Monkeypatched MLflow)
# ---------------------------------------------------------------------------

class TestCacheFallback:
    def test_cache_fallback_list(self, monkeypatch, tenant_id):
        engine = _get_sync_engine()
        schema = _schema(tenant_id)
        with engine.begin() as conn:
            conn.execute(sa.text(f"""
                INSERT INTO {schema}.model_versions
                    (id, tenant_id, version_number, training_job_id, status, metrics, mlflow_run_id)
                VALUES (:id, :tid, :vn, :tjid, :st, :met, :rid)
            """), {
                "id": "cached-1",
                "tid": tenant_id,
                "vn": 1,
                "tjid": "cached-job",
                "st": "completed",
                "met": json.dumps({"eval_f1": 0.85}),
                "rid": "run-cached",
            })

        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise Exception("MLflow unreachable")
                def get_run(self, run_id):
                    raise Exception("MLflow unreachable")
            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)
        result, warning = list_model_versions(tenant_id)
        assert len(result) >= 1
        assert result[0]["version_number"] == 1
        assert warning == "mlflow-unavailable"

    def test_cache_fallback_active(self, monkeypatch, tenant_id):
        engine = _get_sync_engine()
        schema = _schema(tenant_id)
        with engine.begin() as conn:
            conn.execute(sa.text(f"""
                INSERT INTO {schema}.model_versions
                    (id, tenant_id, version_number, training_job_id, status, metrics, mlflow_run_id)
                VALUES (:id, :tid, :vn, :tjid, :st, :met, :rid)
            """), {
                "id": "cached-active-1",
                "tid": tenant_id,
                "vn": 2,
                "tjid": "cached-active-job",
                "st": "promoted",
                "met": json.dumps({"eval_f1": 0.92}),
                "rid": "run-cached-active",
            })

        def mock_client(*args, **kwargs):
            class MockMlflowClient:
                def get_registered_model(self, name):
                    raise Exception("MLflow unreachable")
                def get_run(self, run_id):
                    raise Exception("MLflow unreachable")
            return MockMlflowClient()

        monkeypatch.setattr("src.training_service.infra.mlflow_registry.MlflowClient", mock_client)
        result, warning = get_active_model(tenant_id)
        assert result is not None
        assert result["version_number"] == 2
        assert result["status"] == "promoted"
        assert warning == "mlflow-unavailable"


# ---------------------------------------------------------------------------
# Layer 6: Tenant Isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_tenant_isolation(self, mlflow_client, experiment_name, registered_model_name, tenant_id):
        other_tid = f"other-{uuid.uuid4().hex[:8]}"
        other_model_name = _registered_model_name(other_tid)

        run, exp_id = _create_run(mlflow_client, experiment_name,
                                   tags={"tenant_id": tenant_id},
                                   params={"training_job_id": "test-job-isolation"})
        _complete_run(mlflow_client, run, metrics={"eval_f1": 0.87})

        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv = mlflow_client.create_model_version(name=registered_model_name, source=model_uri, run_id=run.info.run_id)
        mlflow_client.transition_model_version_stage(name=registered_model_name, version=mv.version, stage="Staging")

        assert _registered_model_name(tenant_id) != _registered_model_name(other_tid)
        assert registered_model_name == f"tenant_{tenant_id}_ner_model"
        assert other_model_name == f"tenant_{other_tid}_ner_model"

        a_result, _ = list_model_versions(tenant_id)
        assert len(a_result) >= 1
        assert a_result[0]["mlflow_run_id"] == run.info.run_id

        b_result, _ = list_model_versions(other_tid)
        if b_result:
            b_run_ids = {v["mlflow_run_id"] for v in b_result}
            assert run.info.run_id not in b_run_ids


# ---------------------------------------------------------------------------
# Layer 7: Status Mapping
# ---------------------------------------------------------------------------

class TestStatusMapping:
    def test_status_to_stage_mapping(self):
        assert STATUS_TO_STAGE["completed"] == "Staging"
        assert STATUS_TO_STAGE["promoted"] == "Production"
        assert STATUS_TO_STAGE["archived"] == "Archived"

    def test_stage_to_status_mapping(self):
        assert STAGE_TO_STATUS["Staging"] == "completed"
        assert STAGE_TO_STATUS["Production"] == "promoted"
        assert STAGE_TO_STATUS["Archived"] == "archived"

    def test_roundtrip(self):
        for status, stage in STATUS_TO_STAGE.items():
            assert STAGE_TO_STATUS[stage] == status
