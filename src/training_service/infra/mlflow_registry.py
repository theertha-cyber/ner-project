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


def _metrics_with_label_list(run_metrics: dict, run_params: dict) -> dict:
    metrics = dict(run_metrics)
    raw_label_list = run_params.get("label_list")
    if raw_label_list:
        try:
            metrics["label_list"] = json.loads(raw_label_list)
        except (TypeError, ValueError):
            pass
    return metrics


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
                    (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, mlflow_run_id, created_at, promoted_at)
                VALUES (:id, :tenant_id, :version_number, :training_job_id, :status,
                        CAST(:metrics AS jsonb), :artifact_path, :mlflow_run_id, :created_at, :promoted_at)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    metrics = EXCLUDED.metrics,
                    artifact_path = EXCLUDED.artifact_path,
                    mlflow_run_id = EXCLUDED.mlflow_run_id,
                    promoted_at = COALESCE({schema}.model_versions.promoted_at, EXCLUDED.promoted_at)
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
                "promoted_at": version_data.get("promoted_at") if version_data["status"] == "promoted" else None,
            },
        )


def _lookup_run_number(tenant_id: str, version_number: int) -> int | None:
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT run_number FROM {schema}.model_versions WHERE tenant_id = :tid AND version_number = :vn"),
            {"tid": tenant_id, "vn": version_number},
        )
        row = result.fetchone()
        return row[0] if row else None


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
        all_versions = client.search_model_versions(f"name='{registered_model}'")

        versions = []
        for version in all_versions:
            run = client.get_run(version.run_id)
            run_metrics = run.data.metrics
            run_params = run.data.params
            status = STAGE_TO_STATUS.get(version.current_stage, "completed")
            versions.append({
                "id": version.version,
                "version_number": int(version.version),
                "training_job_id": run_params.get("training_job_id"),
                "status": status,
                "metrics": _metrics_with_label_list(run_metrics, run_params),
                "artifact_path": run_params.get("artifact_path"),
                "mlflow_run_id": version.run_id,
                "mlflow_run_url": _mlflow_run_url(version.run_id),
                "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
            })

        try:
            for v in versions:
                v["run_number"] = _lookup_run_number(tenant_id, v["version_number"])
        except Exception:
            for v in versions:
                v.setdefault("run_number", None)

        try:
            for v in versions:
                _cache_model_version(tenant_id, v)
        except Exception:
            pass

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
            "metrics": _metrics_with_label_list(run_metrics, run_params),
            "artifact_path": run_params.get("artifact_path"),
            "mlflow_run_id": version.run_id,
            "mlflow_run_url": _mlflow_run_url(version.run_id),
            "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
            # last_updated_timestamp bumps whenever this version's stage
            # transitions (e.g. to Production), so it's the closest available
            # proxy for "when this version was promoted" — MLflow has no
            # dedicated promoted-at field.
            "promoted_at": datetime.fromtimestamp(int(version.last_updated_timestamp) / 1000, tz=timezone.utc) if version.last_updated_timestamp else None,
        }
        try:
            result["run_number"] = _lookup_run_number(tenant_id, result["version_number"])
        except Exception:
            result["run_number"] = None
        try:
            _cache_model_version(tenant_id, result)
        except Exception:
            pass
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
        "metrics": _metrics_with_label_list(run_metrics, run_params),
        "artifact_path": run_params.get("artifact_path"),
        "mlflow_run_id": version.run_id,
        "mlflow_run_url": _mlflow_run_url(version.run_id),
        "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
        "promoted_at": datetime.fromtimestamp(int(version.last_updated_timestamp) / 1000, tz=timezone.utc) if version.last_updated_timestamp else None,
    }
    try:
        result["run_number"] = _lookup_run_number(tenant_id, result["version_number"])
    except Exception:
        result["run_number"] = None
    try:
        _cache_model_version(tenant_id, result)
    except Exception:
        pass
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
        "metrics": _metrics_with_label_list(run_metrics, run_params),
        "artifact_path": run_params.get("artifact_path"),
        "mlflow_run_id": version.run_id,
        "mlflow_run_url": _mlflow_run_url(version.run_id),
        "created_at": datetime.fromtimestamp(int(version.creation_timestamp) / 1000, tz=timezone.utc) if version.creation_timestamp else None,
    }
    try:
        result["run_number"] = _lookup_run_number(tenant_id, result["version_number"])
    except Exception:
        result["run_number"] = None
    try:
        _cache_model_version(tenant_id, result)
    except Exception:
        pass
    return result
