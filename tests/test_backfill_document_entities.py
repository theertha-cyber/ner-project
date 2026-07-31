import os
import uuid

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

import pytest
from sqlalchemy import text

import scripts.backfill_document_entities as backfill_module
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
class TestBackfillDocumentEntities:
    """Covers verification.md rows 20-22."""

    async def _setup(self, engine, sync_engine, tid, schema):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE "{schema}".document_text_spans (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, span_index INTEGER,
                    text TEXT, char_start INTEGER, page_number INTEGER
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
                    page_number INTEGER, char_start INTEGER, char_end INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))

    def _teardown(self, engine_sync, schema):
        with engine_sync.begin() as conn:
            for tbl in ("document_entities", "extracted_entities", "document_text_spans"):
                conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".{tbl}'))

    async def test_backfill_populates_normalized_store_leaving_raw_rows_unchanged(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"backfill-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema)

        doc_id = "doc-backfill-1"
        with sync_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{schema}".document_text_spans (id, document_id, span_index, text, char_start, page_number) '
                     "VALUES (:id, :doc_id, 0, 'Arjun Jayakumar works at InApp', 0, 1)"),
                {"id": "span-0", "doc_id": doc_id},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".extracted_entities (id, run_id, document_id, entity_id, value, confidence) '
                     "VALUES (:id, 'run-old', :doc_id, 'B-PER', 'Arjun', 0.9)"),
                {"id": "ee-old-1", "doc_id": doc_id},
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

        monkeypatch.setattr(backfill_module.requests, "post", mock_post)
        monkeypatch.setattr(backfill_module, "create_access_token", lambda **kwargs: "fake-token")

        try:
            with sync_engine.begin() as conn:
                doc_ids = backfill_module._documents_needing_backfill(conn, schema)
                assert doc_ids == [doc_id]

            with sync_engine.begin() as conn:
                ok = backfill_module.backfill_document(conn, schema, tid, doc_id, dry_run=False)
                assert ok is True

            with sync_engine.begin() as conn:
                raw_count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".extracted_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).scalar()
                assert raw_count == 1

                norm_rows = conn.execute(
                    text(f'SELECT entity_type, entity_value FROM "{schema}".document_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).fetchall()
                assert len(norm_rows) == 2

            # Re-running backfill for an already-backfilled document is a no-op on row count.
            with sync_engine.begin() as conn:
                doc_ids_after = backfill_module._documents_needing_backfill(conn, schema)
                assert doc_ids_after == []

            with sync_engine.begin() as conn:
                backfill_module.backfill_document(conn, schema, tid, doc_id, dry_run=False)

            with sync_engine.begin() as conn:
                norm_rows_after = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".document_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).scalar()
                assert norm_rows_after == 2
        finally:
            self._teardown(sync_engine, schema)
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
            sync_engine.dispose()

    async def test_dry_run_reports_without_writing(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"backfill-dryrun-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema)

        doc_id = "doc-dryrun-1"
        with sync_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{schema}".document_text_spans (id, document_id, span_index, text, char_start, page_number) '
                     "VALUES (:id, :doc_id, 0, 'Kerala', 0, 1)"),
                {"id": "span-0", "doc_id": doc_id},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".extracted_entities (id, run_id, document_id, entity_id, value, confidence) '
                     "VALUES (:id, 'run-old', :doc_id, 'B-LOC', 'Kerala', 0.9)"),
                {"id": "ee-old-2", "doc_id": doc_id},
            )

        try:
            with sync_engine.begin() as conn:
                ok = backfill_module.backfill_document(conn, schema, tid, doc_id, dry_run=True)
                assert ok is True

            with sync_engine.begin() as conn:
                norm_count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".document_entities WHERE document_id = :doc_id'),
                    {"doc_id": doc_id},
                ).scalar()
                assert norm_count == 0
        finally:
            self._teardown(sync_engine, schema)
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
            sync_engine.dispose()
