"""Regression tests for `_get_active_model_version`.

The already-extracted check compares against `extraction_runs.model_version`, which
model_serving stamps from the training-service registry. If the extraction service
resolves the active version any other way, the two can disagree and every document
looks never-extracted.

The original defect: the function read `model_versions.version`, a legacy column that
is NULL on every row (the live column is `version_number`). `fetchone()` returned the
truthy tuple `(None,)`, so `str(row[0])` produced the literal string `"None"`, which
matched no extraction run — the picker offered already-extracted documents and the
worker's skip set was always empty.
"""
import os
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")

import requests

from src.extraction_service.worker import _get_active_model_version, _get_cached_model_version
from src.extraction_service.services.entity_store import _schema, get_already_extracted


WORKER = "src.extraction_service.worker"


@pytest_asyncio.fixture
async def model_registry_tenant():
    """Tenant schema whose `model_versions` matches the production shape: legacy
    `version` column present but NULL, real value in `version_number`."""
    engine = create_async_engine(os.environ["NER_DATABASE_URL"], isolation_level="AUTOCOMMIT")
    tid = f"mv-{uuid.uuid4().hex[:12]}"
    schema = _schema(tid)

    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(f"""
            CREATE TABLE "{schema}".model_versions (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                version INTEGER,
                version_number INTEGER,
                status VARCHAR(20) DEFAULT 'candidate'
            )
        """))
        await conn.execute(text(f"""
            CREATE TABLE "{schema}".extraction_runs (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                model_version VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'completed'
            )
        """))
        await conn.execute(text(f"""
            CREATE TABLE "{schema}".extracted_entities (
                id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL REFERENCES "{schema}".extraction_runs(id) ON DELETE CASCADE,
                document_id VARCHAR,
                entity_id VARCHAR NOT NULL
            )
        """))

    yield {"tid": tid, "schema": schema, "engine": engine}

    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await engine.dispose()


async def _promote(engine, schema, tid, version_number):
    """Promoted cache row exactly as production stores it — `version` NULL."""
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO "{schema}".model_versions (id, tenant_id, version, version_number, status)
                VALUES (:id, :tid, NULL, :vn, 'promoted')
            """),
            {"id": str(uuid.uuid4()), "tid": tid, "vn": version_number},
        )


async def _record_extraction(engine, schema, doc_id, model_version):
    run_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f'INSERT INTO "{schema}".extraction_runs (id, tenant_id, model_version) VALUES (:id, :tid, :mv)'),
            {"id": run_id, "tid": "irrelevant", "mv": model_version},
        )
        await conn.execute(
            text(f'INSERT INTO "{schema}".extracted_entities (id, run_id, document_id, entity_id) VALUES (:id, :rid, :did, \'PER\')'),
            {"id": str(uuid.uuid4()), "rid": run_id, "did": doc_id},
        )


def _registry_response(version_number):
    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"id": str(version_number), "version_number": version_number, "status": "promoted"}

    return _Resp()


@pytest.mark.asyncio
class TestRegistryIsTheAuthority:
    async def test_uses_the_registry_version_number(self, model_registry_tenant):
        t = model_registry_tenant
        # Cache deliberately disagrees with the registry, as it did in production.
        await _promote(t["engine"], t["schema"], t["tid"], 1)

        with patch(f"{WORKER}.requests.get", return_value=_registry_response(5)):
            assert _get_active_model_version(t["tid"]) == "5"

    async def test_registry_version_matches_recorded_runs(self, model_registry_tenant):
        """End-to-end shape of the original bug: documents extracted under the
        registry's active version must come back flagged."""
        t = model_registry_tenant
        await _promote(t["engine"], t["schema"], t["tid"], 1)
        for doc_id in ("doc-a", "doc-b"):
            await _record_extraction(t["engine"], t["schema"], doc_id, "5")

        with patch(f"{WORKER}.requests.get", return_value=_registry_response(5)):
            version = _get_active_model_version(t["tid"])

        assert get_already_extracted(t["tid"], ["doc-a", "doc-b"], version) == {"doc-a", "doc-b"}

    async def test_no_promoted_model_resolves_to_zero(self, model_registry_tenant):
        t = model_registry_tenant

        with patch(f"{WORKER}.requests.get", return_value=_registry_response(0)):
            assert _get_active_model_version(t["tid"]) == "0"


@pytest.mark.asyncio
class TestCacheFallback:
    async def test_falls_back_to_cached_version_number_when_registry_unreachable(self, model_registry_tenant):
        t = model_registry_tenant
        await _promote(t["engine"], t["schema"], t["tid"], 3)

        with patch(f"{WORKER}.requests.get", side_effect=requests.RequestException("boom")):
            assert _get_active_model_version(t["tid"]) == "3"

    async def test_falls_back_when_registry_returns_non_200(self, model_registry_tenant):
        t = model_registry_tenant
        await _promote(t["engine"], t["schema"], t["tid"], 3)

        class _Resp:
            status_code = 503

            @staticmethod
            def json():
                return {}

        with patch(f"{WORKER}.requests.get", return_value=_Resp()):
            assert _get_active_model_version(t["tid"]) == "3"

    async def test_null_legacy_version_column_never_yields_the_string_none(self, model_registry_tenant):
        """The exact original defect. The promoted row has `version` NULL; the
        resolver must not return `"None"`, which matches no extraction run."""
        t = model_registry_tenant
        await _promote(t["engine"], t["schema"], t["tid"], 7)

        assert _get_cached_model_version(t["tid"]) == "7"

        with patch(f"{WORKER}.requests.get", side_effect=requests.RequestException("boom")):
            resolved = _get_active_model_version(t["tid"])
        assert resolved == "7"
        assert resolved != "None"

    async def test_no_cached_promoted_row_resolves_to_zero(self, model_registry_tenant):
        t = model_registry_tenant

        with patch(f"{WORKER}.requests.get", side_effect=requests.RequestException("boom")):
            assert _get_active_model_version(t["tid"]) == "0"
