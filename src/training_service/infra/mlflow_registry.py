import json
from datetime import datetime, timezone

import mlflow
from mlflow.tracking import MlflowClient
from sqlalchemy import text, create_engine

from src.shared.config import settings


STATUS_TO_STAGE = {
    "completed": "Staging",
    "promoted": "Production",
    "archived": "Archived",
}

STAGE_TO_STATUS = {v: k for k, v in STATUS_TO_STAGE.items()}


def _registered_model_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id}_ner_model"


def _experiment_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def _mlflow_run_url(run_id: str) -> str:
    return f"{settings.mlflow_tracking_uri}/#/runs/{run_id}"


def _get_client() -> MlflowClient:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


def _get_sync_engine():
    return create_engine(settings.database_url_sync)


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


class MLflowRegistryError(Exception):
    pass


def _cache_model_version(tenant_id: str, version_data: dict) -> None:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                INSERT INTO {schema}.model_versions
                    (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, mlflow_run_id, created_at)
                VALUES (:id, :tenant_id, :version_number, :training_job_id, :status,
                        CAST(:metrics AS jsonb), :artifact_path, :mlflow_run_id, :created_at)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    metrics = EXCLUDED.metrics,
                    artifact_path = EXCLUDED.artifact_path,
                    mlflow_run_id = EXCLUDED.mlflow_run_id
            """),
            {
                "id": version_data["id"],
                "tenant_id": tenant_id,
                "version_number": version_data["version_number"],
                "training_job_id": version_data.get("training_job_id"),
                "status": version_data["status"],
                "metrics": json.dumps(version_data.get("metrics") or {}),
                "artifact_path": version_data.get("artifact_path"),
                "mlflow_run_id": version_data.get("mlflow_run_id"),
                "created_at": version_data.get("created_at", datetime.now(timezone.utc)),
            },
        )


def _read_cache_model_versions(tenant_id: str) -> list[dict]:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT * FROM {schema}.model_versions WHERE tenant_id = :tid ORDER BY version_number DESC"),
            {"tid": tenant_id},
        )
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]


def _read_cache_active_model(tenant_id: str) -> dict | None:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT * FROM {schema}.model_versions WHERE tenant_id = :tid AND status = 'promoted' ORDER BY version_number DESC LIMIT 1"),
            {"tid": tenant_id},
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None


def list_model_versions(tenant_id: str) -> tuple[list[dict], str | None]:
    warning = None
    try:
        client = _get_client()
        registered_model = _registered_model_name(tenant_id)
        try:
            mv = client.get_registered_model(registered_model)
        except mlflow.exceptions.RestException:
            return [], None

        versions = []
        for version in mv.latest_versions:
            run = client.get_run(version.run_id)
            run_metrics = run.data.metrics
            run_params = run.data.params
            status = STAGE_TO_STATUS.get(version.current_stage, "completed")
            versions.append({
                "id": version.version,
                "version_number": int(version.version),
                "training_job_id": run_params.get("training_job_id"),
                "status": status,
                "metrics": dict(run_metrics),
                "artifact_path": run_params.get("artifact_path"),
                "mlflow_run_id": version.run_id,
                "mlflow_run_url": _mlflow_run_url(version.run_id),
                "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
            })

        for v in versions:
            _cache_model_version(tenant_id, v)

        return sorted(versions, key=lambda v: v["version_number"], reverse=True), None

    except Exception:
        warning = "mlflow-unavailable"
        cached = _read_cache_model_versions(tenant_id)
        return cached, warning


def get_active_model(tenant_id: str) -> tuple[dict | None, str | None]:
    warning = None
    try:
        client = _get_client()
        registered_model = _registered_model_name(tenant_id)
        try:
            mv = client.get_registered_model(registered_model)
        except mlflow.exceptions.RestException:
            return None, None

        production_versions = [v for v in mv.latest_versions if v.current_stage == "Production"]
        if not production_versions:
            return None, None

        version = production_versions[0]
        run = client.get_run(version.run_id)
        run_metrics = run.data.metrics
        run_params = run.data.params
        result = {
            "id": version.version,
            "version_number": int(version.version),
            "training_job_id": run_params.get("training_job_id"),
            "status": "promoted",
            "metrics": dict(run_metrics),
            "artifact_path": run_params.get("artifact_path"),
            "mlflow_run_id": version.run_id,
            "mlflow_run_url": _mlflow_run_url(version.run_id),
            "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
        }
        _cache_model_version(tenant_id, result)
        return result, None

    except Exception:
        warning = "mlflow-unavailable"
        cached = _read_cache_active_model(tenant_id)
        if cached:
            cached["mlflow_run_url"] = _mlflow_run_url(cached["mlflow_run_id"]) if cached.get("mlflow_run_id") else None
        return cached, warning


def promote_model_version(tenant_id: str, version_number: int) -> dict | None:
    client = _get_client()
    registered_model = _registered_model_name(tenant_id)

    try:
        client.get_registered_model(registered_model)
    except mlflow.exceptions.RestException:
        return None

    production_versions = client.get_latest_versions(registered_model, stages=["Production"])
    for pv in production_versions:
        client.transition_model_version_stage(
            name=registered_model,
            version=pv.version,
            stage="Archived",
        )

    client.transition_model_version_stage(
        name=registered_model,
        version=str(version_number),
        stage="Production",
    )

    version = client.get_model_version(name=registered_model, version=str(version_number))
    run = client.get_run(version.run_id)
    run_metrics = run.data.metrics
    run_params = run.data.params
    result = {
        "id": version.version,
        "version_number": int(version.version),
        "training_job_id": run_params.get("training_job_id"),
        "status": "promoted",
        "metrics": dict(run_metrics),
        "artifact_path": run_params.get("artifact_path"),
        "mlflow_run_id": version.run_id,
        "mlflow_run_url": _mlflow_run_url(version.run_id),
        "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
    }
    _cache_model_version(tenant_id, result)
    return result


def demote_model_version(tenant_id: str, version_number: int) -> dict | None:
    client = _get_client()
    registered_model = _registered_model_name(tenant_id)

    try:
        client.get_registered_model(registered_model)
    except mlflow.exceptions.RestException:
        return None

    client.transition_model_version_stage(
        name=registered_model,
        version=str(version_number),
        stage="Staging",
    )

    version = client.get_model_version(name=registered_model, version=str(version_number))
    run = client.get_run(version.run_id)
    run_metrics = run.data.metrics
    run_params = run.data.params
    result = {
        "id": version.version,
        "version_number": int(version.version),
        "training_job_id": run_params.get("training_job_id"),
        "status": "completed",
        "metrics": dict(run_metrics),
        "artifact_path": run_params.get("artifact_path"),
        "mlflow_run_id": version.run_id,
        "mlflow_run_url": _mlflow_run_url(version.run_id),
        "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
    }
    _cache_model_version(tenant_id, result)
    return result
