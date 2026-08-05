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
class TestWorkerNormalizesEntitiesOnIngest:
    """Covers verification.md rows 16-19, 25 — normalized entities are persisted
    alongside raw BIO rows in the same transaction, one row per logical entity."""

    async def test_batch_extraction_persists_normalized_entities(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"norm-persist-{uuid.uuid4().hex[:8]}"
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

        doc_id = "doc-normalize-1"
        run_id = "run-normalize-1"
        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE "{schema}".documents (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'processed'
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
                     "VALUES (:id, :doc_id, 0, 'Arjun Jayakumar works at InApp', 0, 1)"),
                {"id": "span-0", "doc_id": doc_id},
            )

        def mock_post(url, headers=None, json=None, timeout=None):
            return _FakeResponse({
                "predictions": [
                    {"token": "Arjun", "label": "B-PER", "confidence": 0.95},
                    {"token": "Jayakumar", "label": "I-PER", "confidence": 0.90},
                    {"token": "InApp", "label": "B-ORG", "confidence": 0.85},
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
                raw_rows = conn.execute(
                    text(f'SELECT entity_id, value FROM "{schema}".extracted_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).fetchall()
                assert len(raw_rows) == 3
                assert all(r[0] in ("B-PER", "I-PER", "B-ORG") for r in raw_rows)

                norm_rows = conn.execute(
                    text(f'SELECT entity_type, entity_value, normalized_value FROM "{schema}".document_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).fetchall()
                assert len(norm_rows) == 2
                by_type = {r[0]: r for r in norm_rows}
                assert by_type["PER"][1] == "Arjun Jayakumar"
                assert by_type["ORG"][1] == "InApp"
                assert by_type["ORG"][2] == "inapp"
                assert not any(r[0].startswith("B-") or r[0].startswith("I-") for r in norm_rows)
        finally:
            with sync_engine.begin() as conn:
                for tbl in ("document_entities", "extracted_entities", "extraction_runs", "model_versions", "document_text_spans", "documents"):
                    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".{tbl}'))
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
            sync_engine.dispose()

    async def test_persistence_failure_leaves_no_rows_in_either_table(self, monkeypatch, engine, setup_database):
        """Covers verification.md row 19: a failure while inserting normalized entities
        must roll back the raw-entity inserts too, since both happen in one transaction."""
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"norm-atomic-{uuid.uuid4().hex[:8]}"
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

        doc_id = "doc-atomic-1"
        run_id = "run-atomic-1"
        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE "{schema}".documents (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'processed'
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
            # Note: document_entities intentionally NOT created, so the insert inside
            # the worker's transaction raises and must roll back the raw inserts too.
            conn.execute(
                text(f'INSERT INTO "{schema}".extraction_runs (id, tenant_id, document_id, model_version, status, started_at) '
                     "VALUES (:id, :tid, NULL, '0', 'running', now())"),
                {"id": run_id, "tid": tid},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".documents (id, tenant_id, filename, status) VALUES (:id, :tid, :fn, \'processed\')'),
                {"id": doc_id, "tid": tid, "fn": "a.pdf"},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".document_text_spans (id, document_id, span_index, text, char_start, page_number) '
                     "VALUES (:id, :doc_id, 0, 'Arjun Jayakumar', 0, 1)"),
                {"id": "span-0", "doc_id": doc_id},
            )

        def mock_post(url, headers=None, json=None, timeout=None):
            return _FakeResponse({
                "predictions": [
                    {"token": "Arjun", "label": "B-PER", "confidence": 0.95},
                    {"token": "Jayakumar", "label": "I-PER", "confidence": 0.90},
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
                raw_count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".extracted_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).scalar()
                assert raw_count == 0

                run_row = conn.execute(
                    text(f'SELECT failed_count, processed_count FROM "{schema}".extraction_runs WHERE id = :run_id'),
                    {"run_id": run_id},
                ).fetchone()
                assert run_row.failed_count == 1
                assert run_row.processed_count == 0
        finally:
            with sync_engine.begin() as conn:
                for tbl in ("extracted_entities", "extraction_runs", "model_versions", "document_text_spans", "documents"):
                    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".{tbl}'))
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
            sync_engine.dispose()
