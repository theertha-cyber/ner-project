import os
import uuid

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

import pytest
from sqlalchemy import text

from src.extraction_service import worker as worker_module
from src.extraction_service.services import semantic_normalizer
from src.extraction_service.services.entity_store import _schema
from src.extraction_service.services.semantic_normalizer import StructuredValue


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _temperature_parser(text_value: str, unit: str | None) -> StructuredValue | None:
    """Throwaway parser for a kind that does not exist in production — proves a new
    kind can be registered without editing the worker, the store, the migrations, or
    the SQL whitelist. Covers verification.md scenario 6."""
    stripped = text_value.strip().rstrip("C").rstrip("c").strip()
    try:
        value = float(stripped)
    except ValueError:
        return None
    return StructuredValue(value_kind="temperature", number=value, unit=unit or "celsius")


@pytest.mark.asyncio
class TestNewKindRequiresNoPipelineChange:
    """Covers verification.md row 6."""

    async def test_registering_a_new_kind_persists_typed_values_with_no_pipeline_edit(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        monkeypatch.setattr(semantic_normalizer, "SUPPORTED_KINDS", semantic_normalizer.SUPPORTED_KINDS | {"temperature"})
        monkeypatch.setitem(semantic_normalizer.PARSERS, "temperature", _temperature_parser)

        tid = f"ext-kind-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, version, required_flag, is_active, value_kind, value_unit) "
                    "VALUES (:id, :tid, 'BODY_TEMP', '', 1, false, true, 'temperature', 'celsius')"
                ),
                {"id": str(uuid.uuid4()), "tid": tid},
            )

        doc_id = "doc-ext-1"
        run_id = "run-ext-1"
        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE "{schema}".documents (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'processed',
                    purpose VARCHAR(20) NOT NULL DEFAULT 'query'
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".document_text_spans (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, span_index INTEGER,
                    text TEXT, char_start INTEGER, page_number INTEGER
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".extraction_runs (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, document_id VARCHAR, model_version VARCHAR,
                    status VARCHAR NOT NULL DEFAULT 'queued', started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    completed_at TIMESTAMP WITH TIME ZONE, total_documents INTEGER NOT NULL DEFAULT 0,
                    processed_count INTEGER NOT NULL DEFAULT 0, skipped_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".model_versions (
                    tenant_id VARCHAR, version INTEGER, status VARCHAR
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".extracted_entities (
                    id VARCHAR PRIMARY KEY, run_id VARCHAR, document_id VARCHAR, entity_id VARCHAR,
                    value TEXT, confidence FLOAT, review_status VARCHAR DEFAULT 'unreviewed'
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".document_entities (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    page_number INTEGER, char_start INTEGER, char_end INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    value_kind TEXT, value_number DOUBLE PRECISION, value_number_high DOUBLE PRECISION,
                    value_unit TEXT, value_date DATE, value_date_high DATE
                )
            """))
            conn.execute(
                text(f'INSERT INTO "{schema}".documents (id, tenant_id, filename, status) VALUES (:id, :tid, :fn, \'processed\')'),
                {"id": doc_id, "tid": tid, "fn": "a.pdf"},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".document_text_spans (id, document_id, span_index, text, char_start, page_number) '
                     "VALUES (:id, :doc_id, 0, '37.5C', 0, 1)"),
                {"id": "span-0", "doc_id": doc_id},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".extraction_runs (id, tenant_id, document_id, model_version, status, started_at) '
                     "VALUES (:id, :tid, :doc_id, '0', 'running', now())"),
                {"id": run_id, "tid": tid, "doc_id": doc_id},
            )

        def mock_post(url, headers=None, json=None, timeout=None):
            return _FakeResponse({
                "predictions": [{"token": "37.5C", "label": "B-BODY_TEMP", "confidence": 0.9}],
                "model_version": "0",
            })

        monkeypatch.setattr(worker_module.requests, "post", mock_post)
        monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
        import src.shared.auth as auth_module
        monkeypatch.setattr(auth_module, "create_access_token", lambda **kwargs: "fake-token")

        try:
            worker_module.run_batch_extraction.run(tid, run_id, [doc_id])

            with sync_engine.begin() as conn:
                row = conn.execute(
                    text(f'SELECT value_kind, value_number, value_unit FROM "{schema}".document_entities '
                         "WHERE document_id = :doc_id"),
                    {"doc_id": doc_id},
                ).fetchone()
                assert row.value_kind == "temperature"
                assert row.value_number == 37.5
                assert row.value_unit == "celsius"
        finally:
            with sync_engine.begin() as conn:
                for tbl in ("document_entities", "extracted_entities", "extraction_runs", "model_versions", "document_text_spans", "documents"):
                    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".{tbl}'))
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid})
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
            sync_engine.dispose()
