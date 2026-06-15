"""Live integration tests for MLflow integration.

Requires:
- MLflow Tracking Server running on NER_MLFLOW_TRACKING_URI (default: http://localhost:5000)
- PostgreSQL DB running on NER_DATABASE_URL_SYNC (for cache fallback verification)

These tests use the mlflow_registry module functions + direct MlflowClient
calls to verify the end-to-end MLflow integration without needing the full
Celery / training service stack.
"""
import os
import uuid

import pytest
from mlflow.tracking import MlflowClient
import mlflow
import sqlalchemy as sa

os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:5432/ner_dev")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("NER_MLFLOW_INTEGRATION_TESTS"),
        reason="Set NER_MLFLOW_INTEGRATION_TESTS=1 to run live integration tests",
    ),
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
    _read_cache_model_versions,
)


@pytest.fixture(autouse=True)
def db_schema(tenant_id):
    """Create tenant schema + model_versions table for DB cache writes."""
    sync_url = settings.database_url_sync
    schema = f"tenant_{tenant_id.replace('-', '_')}"
    engine = sa.create_engine(sync_url)
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


@pytest.fixture(scope="module")
def mlflow_client():
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


@pytest.fixture
def tenant_id():
    return f"int-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def registered_model_name(tenant_id):
    return _registered_model_name(tenant_id)


@pytest.fixture
def experiment_name(tenant_id):
    return _experiment_name(tenant_id)


@pytest.fixture(autouse=True)
def cleanup(mlflow_client, registered_model_name, experiment_name):
    yield
    try:
        mlflow_client.delete_registered_model(registered_model_name)
    except Exception:
        pass
    try:
        mlflow_client.delete_experiment(mlflow_client.get_experiment_by_name(experiment_name).experiment_id)
    except Exception:
        pass


class TestMlflowServerLive:
    """Verify MLflow server is reachable and responds correctly."""

    def test_server_health(self):
        """MLflow server responds to health check."""
        import requests
        resp = requests.get(f"{settings.mlflow_tracking_uri}/health", timeout=5)
        assert resp.status_code == 200

    def test_create_experiment(self, mlflow_client, experiment_name):
        """Can create an MLflow experiment."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        assert exp_id is not None
        exp = mlflow_client.get_experiment(exp_id)
        assert exp.name == experiment_name

    def test_create_run_with_params_tags(self, mlflow_client, experiment_name):
        """Run created with params and tags."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id, tags={"test_tag": "test_value", "tenant_id": experiment_name})
        mlflow_client.log_param(run.info.run_id, "learning_rate", 2e-5)
        mlflow_client.log_param(run.info.run_id, "num_epochs", 3)

        run_data = mlflow_client.get_run(run.info.run_id)
        assert run_data.data.params["learning_rate"] == "2e-05"
        assert run_data.data.params["num_epochs"] == "3"
        assert run_data.data.tags.get("test_tag") == "test_value"

        mlflow_client.set_terminated(run.info.run_id)

    def test_log_metrics(self, mlflow_client, experiment_name):
        """Metrics can be logged per-step."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.85, step=0)
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.88, step=1)
        mlflow_client.log_metric(run.info.run_id, "eval_loss", 0.12, step=0)

        run_data = mlflow_client.get_run(run.info.run_id)
        assert float(run_data.data.metrics["eval_f1"]) == 0.88
        assert float(run_data.data.metrics["eval_loss"]) == 0.12
        mlflow_client.set_terminated(run.info.run_id)

    def test_run_failure_status(self, mlflow_client, experiment_name):
        """Run can be set to FAILED with error message."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.set_tag(run.info.run_id, "error_message", "Out of memory")
        mlflow_client.set_terminated(run.info.run_id, status="FAILED")

        run_data = mlflow_client.get_run(run.info.run_id)
        assert run_data.info.status == "FAILED"
        assert run_data.data.tags.get("error_message") == "Out of memory"


class TestModelRegistryProxyLive:
    """Verify model registry proxy works against live MLflow."""

    def test_list_empty_when_no_model(self, tenant_id):
        """list_model_versions returns empty when no registered model exists."""
        result, warning = list_model_versions(tenant_id)
        assert result == []
        assert warning is None

    def test_register_and_list_model(self, mlflow_client, tenant_id, registered_model_name, experiment_name):
        """Can register a model and see it via the proxy."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.log_param(run.info.run_id, "training_job_id", "test-job-123")
        mlflow_client.log_param(run.info.run_id, "artifact_path", "s3://bucket/test")
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.87)
        mlflow_client.log_metric(run.info.run_id, "eval_precision", 0.85)
        mlflow_client.log_metric(run.info.run_id, "eval_recall", 0.89)
        mlflow_client.set_terminated(run.info.run_id)

        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)
        mv = mlflow_client.create_model_version(
            name=registered_model_name,
            source=model_uri,
            run_id=run.info.run_id,
        )

        result, warning = list_model_versions(tenant_id)
        assert len(result) >= 1
        matching = [v for v in result if v["version_number"] == int(mv.version)]
        assert len(matching) >= 1
        assert matching[0]["mlflow_run_id"] == run.info.run_id
        assert matching[0]["status"] == "completed"

    def test_promote_and_get_active(self, mlflow_client, tenant_id, registered_model_name, experiment_name):
        """Promote a model and verify it shows as active."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.log_param(run.info.run_id, "training_job_id", "test-job-promote")
        mlflow_client.log_param(run.info.run_id, "artifact_path", "s3://bucket/promote-test")
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.92)
        mlflow_client.set_terminated(run.info.run_id)

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

    def test_demote_active(self, mlflow_client, tenant_id, registered_model_name, experiment_name):
        """Demote a promoted model back to completed."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run = mlflow_client.create_run(exp_id)
        mlflow_client.log_param(run.info.run_id, "training_job_id", "test-job-demote")
        mlflow_client.log_param(run.info.run_id, "artifact_path", "s3://bucket/demote-test")
        mlflow_client.log_metric(run.info.run_id, "eval_f1", 0.90)
        mlflow_client.set_terminated(run.info.run_id)

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
            stage="Production",
        )

        result = demote_model_version(tenant_id, int(mv.version))
        assert result is not None
        assert result["status"] == "completed"

        active, warning = get_active_model(tenant_id)
        assert active is None

    def test_promote_archives_previous(self, mlflow_client, tenant_id, registered_model_name, experiment_name):
        """Promoting a new version archives the previous Production version."""
        exp_id = mlflow_client.create_experiment(experiment_name)
        run1 = mlflow_client.create_run(exp_id)
        mlflow_client.log_param(run1.info.run_id, "training_job_id", "test-job-v1")
        mlflow_client.log_param(run1.info.run_id, "artifact_path", "s3://bucket/v1")
        mlflow_client.log_metric(run1.info.run_id, "eval_f1", 0.85)
        mlflow_client.set_terminated(run1.info.run_id)

        run2 = mlflow_client.create_run(exp_id)
        mlflow_client.log_param(run2.info.run_id, "training_job_id", "test-job-v2")
        mlflow_client.log_param(run2.info.run_id, "artifact_path", "s3://bucket/v2")
        mlflow_client.log_metric(run2.info.run_id, "eval_f1", 0.92)
        mlflow_client.set_terminated(run2.info.run_id)

        model_uri1 = f"runs:/{run1.info.run_id}/model"
        model_uri2 = f"runs:/{run2.info.run_id}/model"
        mlflow_client.create_registered_model(registered_model_name)

        mv1 = mlflow_client.create_model_version(
            name=registered_model_name, source=model_uri1, run_id=run1.info.run_id,
        )
        mv2 = mlflow_client.create_model_version(
            name=registered_model_name, source=model_uri2, run_id=run2.info.run_id,
        )

        mlflow_client.transition_model_version_stage(
            name=registered_model_name, version=mv1.version, stage="Production",
        )

        promote_model_version(tenant_id, int(mv2.version))

        v1_details = mlflow_client.get_model_version(registered_model_name, mv1.version)
        assert v1_details.current_stage == "Archived"

        active, _ = get_active_model(tenant_id)
        assert active["version_number"] == int(mv2.version)
