"""Tests for training worker functions: _update_job_progress and model_versions lifecycle."""
import uuid
import json

import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.pool import NullPool

import os
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings
from src.training_service.worker import _update_job_progress, _schema, _get_sync_engine


def _create_test_schema(schema: str):
    engine = _get_sync_engine()
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.training_jobs (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                status VARCHAR(20) DEFAULT 'queued',
                metrics JSONB,
                error_message TEXT,
                run_number INTEGER,
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                failed_at TIMESTAMPTZ,
                model_version_id VARCHAR,
                mlflow_run_id VARCHAR,
                mlflow_run_url VARCHAR
            )
        """))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.model_versions (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                version_number INTEGER NOT NULL,
                training_job_id VARCHAR,
                status VARCHAR(20) DEFAULT 'training',
                metrics JSONB,
                artifact_path TEXT,
                mlflow_run_id VARCHAR,
                mlflow_run_url VARCHAR,
                promoted_at TIMESTAMPTZ,
                archived_at TIMESTAMPTZ,
                run_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))


def _cleanup_test_schema(schema: str):
    engine = _get_sync_engine()
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))


class TestUpdateJobProgress:
    def setup_method(self):
        self.tenant_id = str(uuid.uuid4())
        self.schema = _schema(self.tenant_id)
        self.job_id = str(uuid.uuid4())
        _create_test_schema(self.schema)
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"INSERT INTO {self.schema}.training_jobs (id, tenant_id, status) VALUES (:id, :tid, 'running')"),
                {"id": self.job_id, "tid": self.tenant_id},
            )

    def teardown_method(self):
        _cleanup_test_schema(self.schema)

    def test_update_with_dict_metrics(self):
        metrics = {"f1": 0.5, "loss": 0.1}
        _update_job_progress(self.tenant_id, self.job_id, status="completed", metrics=metrics)

        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT status, metrics FROM {self.schema}.training_jobs WHERE id = :id"),
                {"id": self.job_id},
            ).fetchone()
            assert row[0] == "completed"
            result = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            assert result == {"f1": 0.5, "loss": 0.1}

    def test_update_with_string_metrics(self):
        metrics_str = json.dumps({"f1": 0.5})
        _update_job_progress(self.tenant_id, self.job_id, status="completed", metrics=metrics_str)

        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT metrics FROM {self.schema}.training_jobs WHERE id = :id"),
                {"id": self.job_id},
            ).fetchone()
            result = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            assert result == {"f1": 0.5}

    def test_update_with_none_metrics(self):
        _update_job_progress(self.tenant_id, self.job_id, status="completed", metrics=None)

        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT metrics FROM {self.schema}.training_jobs WHERE id = :id"),
                {"id": self.job_id},
            ).fetchone()
            assert row[0] is None

    def test_update_with_mixed_fields(self):
        _update_job_progress(
            self.tenant_id, self.job_id,
            status="completed",
            metrics={"f1": 0.5},
            error_message=None,
            model_version_id=str(uuid.uuid4()),
        )

        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT status, metrics, error_message FROM {self.schema}.training_jobs WHERE id = :id"),
                {"id": self.job_id},
            ).fetchone()
            assert row[0] == "completed"
            result = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            assert result == {"f1": 0.5}
            assert row[2] is None


class TestModelVersionsStatusLifecycle:
    def setup_method(self):
        self.tenant_id = str(uuid.uuid4())
        self.schema = _schema(self.tenant_id)
        self.job_id = str(uuid.uuid4())
        self.version_id = str(uuid.uuid4())
        _create_test_schema(self.schema)
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"INSERT INTO {self.schema}.training_jobs (id, tenant_id, status) VALUES (:id, :tid, 'running')"),
                {"id": self.job_id, "tid": self.tenant_id},
            )

    def teardown_method(self):
        _cleanup_test_schema(self.schema)

    def _insert_model_version(self, status: str):
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {self.schema}.model_versions
                        (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, created_at)
                    VALUES (:id, :tid, :vn, :tjid, :st, CAST(:metrics AS jsonb), :path, :now)
                """),
                {
                    "id": self.version_id,
                    "tid": self.tenant_id,
                    "vn": 1,
                    "tjid": self.job_id,
                    "st": status,
                    "metrics": json.dumps({}),
                    "path": "test/path",
                    "now": datetime.now(timezone.utc),
                },
            )

    def _get_model_version_status(self):
        engine = _get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT status FROM {self.schema}.model_versions WHERE id = :id"),
                {"id": self.version_id},
            ).fetchone()
            return row[0] if row else None

    def test_insert_with_training_status(self):
        self._insert_model_version("training")
        assert self._get_model_version_status() == "training"

    def test_update_to_completed(self):
        self._insert_model_version("training")
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE {self.schema}.model_versions SET status = 'completed' WHERE id = :id AND tenant_id = :tid"),
                {"id": self.version_id, "tid": self.tenant_id},
            )
        assert self._get_model_version_status() == "completed"

    def test_update_to_failed(self):
        self._insert_model_version("training")
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE {self.schema}.model_versions SET status = 'failed' WHERE id = :id AND tenant_id = :tid"),
                {"id": self.version_id, "tid": self.tenant_id},
            )
        assert self._get_model_version_status() == "failed"

    def test_status_transitions_training_to_completed(self):
        self._insert_model_version("training")
        _update_job_progress(self.tenant_id, self.job_id, status="completed", metrics={"f1": 0.5})
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE {self.schema}.model_versions SET status = 'completed' WHERE id = :id AND tenant_id = :tid"),
                {"id": self.version_id, "tid": self.tenant_id},
            )
        assert self._get_model_version_status() == "completed"

    def test_status_transitions_training_to_failed(self):
        self._insert_model_version("training")
        _update_job_progress(self.tenant_id, self.job_id, status="failed", error_message="training failed")
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE {self.schema}.model_versions SET status = 'failed' WHERE id = :id AND tenant_id = :tid"),
                {"id": self.version_id, "tid": self.tenant_id},
            )
        assert self._get_model_version_status() == "failed"


class TestModelVersionRunNumberInheritance:
    """Mirrors the run_number lookup/insert worker.py performs on job completion (see worker.py:363-409)."""

    def setup_method(self):
        self.tenant_id = str(uuid.uuid4())
        self.schema = _schema(self.tenant_id)
        self.job_id = str(uuid.uuid4())
        _create_test_schema(self.schema)

    def teardown_method(self):
        _cleanup_test_schema(self.schema)

    def test_model_version_inherits_job_run_number(self):
        engine = _get_sync_engine()
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {self.schema}.training_jobs (id, tenant_id, status, run_number)
                    VALUES (:id, :tid, 'running', :run_number)
                """),
                {"id": self.job_id, "tid": self.tenant_id, "run_number": 7},
            )

        with engine.connect() as conn:
            job_run_number_row = conn.execute(
                text(f"SELECT run_number FROM {self.schema}.training_jobs WHERE tenant_id = :tenant_id AND id = :job_id"),
                {"tenant_id": self.tenant_id, "job_id": self.job_id},
            ).fetchone()
            run_number = job_run_number_row[0] if job_run_number_row else None

        assert run_number == 7

        version_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {self.schema}.model_versions
                        (id, tenant_id, version_number, training_job_id, status, run_number, created_at)
                    VALUES (:id, :tid, :vn, :tjid, 'training', :run_number, :now)
                """),
                {
                    "id": version_id, "tid": self.tenant_id, "vn": 1,
                    "tjid": self.job_id, "run_number": run_number,
                    "now": datetime.now(timezone.utc),
                },
            )

        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT run_number FROM {self.schema}.model_versions WHERE id = :id"),
                {"id": version_id},
            ).fetchone()

        assert row[0] == 7
