import os
import uuid

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

import pytest
from sqlalchemy import text

from src.extraction_service import worker as worker_module
from src.extraction_service.services.entity_store import _schema


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.mark.asyncio
class TestWorkerSemanticNormalization:
    """Covers verification.md rows 1, 2, 5, 18, 20, 21."""

    async def _make_tenant_and_schema(self, engine, tid, schema):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    async def _make_entity_definition(self, engine, tid, name, value_kind=None, value_unit=None):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, version, required_flag, is_active, value_kind, value_unit) "
                    "VALUES (:id, :tid, :name, '', 1, false, true, :vk, :vu)"
                ),
                {"id": str(uuid.uuid4()), "tid": tid, "name": name, "vk": value_kind, "vu": value_unit},
            )

    def _create_tenant_tables(self, sync_engine, schema):
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
                    tenant_id VARCHAR, version INTEGER, version_number INTEGER, status VARCHAR
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

    async def test_semantic_and_lexical_normalization_persist_independently(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"sem-norm-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)

        await self._make_tenant_and_schema(engine, tid, schema)
        await self._make_entity_definition(engine, tid, "YEARS_OF_EXP", value_kind="duration", value_unit="years")
        await self._make_entity_definition(engine, tid, "SKILL")  # no value_kind -> stays text

        doc_id = "doc-sem-1"
        run_id = "run-sem-1"
        self._create_tenant_tables(sync_engine, schema)
        with sync_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{schema}".documents (id, tenant_id, filename, status) VALUES (:id, :tid, :fn, \'processed\')'),
                {"id": doc_id, "tid": tid, "fn": "a.pdf"},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".document_text_spans (id, document_id, span_index, text, char_start, page_number) '
                     "VALUES (:id, :doc_id, 0, '5+ years ReactJS several', 0, 1)"),
                {"id": "span-0", "doc_id": doc_id},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".extraction_runs (id, tenant_id, document_id, model_version, status, started_at) '
                     "VALUES (:id, :tid, :doc_id, '0', 'running', now())"),
                {"id": run_id, "tid": tid, "doc_id": doc_id},
            )

        def mock_post(url, headers=None, json=None, timeout=None):
            return _FakeResponse({
                "predictions": [
                    {"token": "5+", "label": "B-YEARS_OF_EXP", "confidence": 0.95},
                    {"token": "years", "label": "I-YEARS_OF_EXP", "confidence": 0.93},
                    {"token": "ReactJS", "label": "B-SKILL", "confidence": 0.9},
                    {"token": "several", "label": "B-YEARS_OF_EXP", "confidence": 0.6},
                ],
                "model_version": "0",
            })

        def mock_create_access_token(**kwargs):
            return "fake-token"

        monkeypatch.setattr(worker_module.requests, "post", mock_post)
        monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
        import src.shared.auth as auth_module
        monkeypatch.setattr(auth_module, "create_access_token", mock_create_access_token)

        try:
            worker_module.run_batch_extraction.run(tid, run_id, [doc_id])

            with sync_engine.begin() as conn:
                rows = conn.execute(
                    text(f'SELECT entity_type, entity_value, normalized_value, value_kind, value_number, '
                         f'value_number_high, value_unit FROM "{schema}".document_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).fetchall()
                assert len(rows) == 3
                by_value = {r.entity_value: r for r in rows}

                # Scenario 1 & 20: typed columns alongside unchanged text columns.
                years_row = by_value["5+ years"]
                assert years_row.entity_type == "YEARS_OF_EXP"
                assert years_row.normalized_value == "5+ years"
                assert years_row.value_kind == "duration"
                assert years_row.value_number == 5.0
                assert years_row.value_number_high is None
                assert years_row.value_unit == "years"

                # Scenario 2 & 5: lexical-only type is fully unaffected.
                skill_row = by_value["ReactJS"]
                assert skill_row.normalized_value == "react"
                assert skill_row.value_kind is None
                assert skill_row.value_number is None

                # Scenario 18: unparseable structured value degrades to NULL, row still persisted.
                junk_row = by_value["several"]
                assert junk_row.entity_type == "YEARS_OF_EXP"
                assert junk_row.normalized_value == "several"
                assert junk_row.value_number is None

                run_row = conn.execute(
                    text(f'SELECT status, failed_count, processed_count FROM "{schema}".extraction_runs WHERE id = :run_id'),
                    {"run_id": run_id},
                ).fetchone()
                assert run_row.status == "completed"
                assert run_row.failed_count == 0
                assert run_row.processed_count == 1

                # Scenario 21: existing normalized_value equality queries still work.
                aws_style = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".document_entities WHERE normalized_value = :v'),
                    {"v": "react"},
                ).scalar()
                assert aws_style == 1
        finally:
            with sync_engine.begin() as conn:
                for tbl in ("document_entities", "extracted_entities", "extraction_runs", "model_versions", "document_text_spans", "documents"):
                    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".{tbl}'))
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid})
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
            sync_engine.dispose()
