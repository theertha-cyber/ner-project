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


@pytest.mark.asyncio
class TestBackfillSemanticValues:
    """Covers verification.md rows 26-28."""

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
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, version, required_flag, is_active, value_kind, value_unit) "
                    "VALUES (:id, :tid, 'YEARS_OF_EXP', '', 1, false, true, 'duration', 'years')"
                ),
                {"id": str(uuid.uuid4()), "tid": tid},
            )

        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE "{schema}".document_entities (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    page_number INTEGER, char_start INTEGER, char_end INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    value_kind TEXT, value_number DOUBLE PRECISION, value_number_high DOUBLE PRECISION,
                    value_unit TEXT, value_date DATE, value_date_high DATE
                )
            """))

    async def _teardown(self, engine, sync_engine, tid, schema):
        with sync_engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".document_entities'))
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await conn.execute(text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid})
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_backfill_populates_typed_values_without_inference(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"sem-bf-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema)

        doc_id = "doc-sem-bf-1"
        de_id = str(uuid.uuid4())
        with sync_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{schema}".document_entities '
                     '(id, document_id, entity_type, entity_value, normalized_value, confidence) '
                     "VALUES (:id, :doc_id, 'YEARS_OF_EXP', '5+ years', '5+ years', 0.9)"),
                {"id": de_id, "doc_id": doc_id},
            )

        def fail_if_called(*args, **kwargs):
            raise AssertionError("semantic backfill must not call model inference")

        monkeypatch.setattr(backfill_module.requests, "post", fail_if_called)

        try:
            with sync_engine.begin() as conn:
                updated = backfill_module.backfill_semantic_values_for_document(conn, schema, tid, doc_id)
            assert updated == 1

            with sync_engine.begin() as conn:
                row = conn.execute(
                    text(f'SELECT value_kind, value_number, value_unit, entity_value, normalized_value, confidence '
                         f'FROM "{schema}".document_entities WHERE id = :id'),
                    {"id": de_id},
                ).fetchone()
                assert row.value_kind == "duration"
                assert row.value_number == 5.0
                assert row.value_unit == "years"
                assert row.entity_value == "5+ years"
                assert row.normalized_value == "5+ years"
                assert row.confidence == 0.9
        finally:
            await self._teardown(engine, sync_engine, tid, schema)
            sync_engine.dispose()

    async def test_backfill_is_idempotent(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"sem-bf-idem-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema)

        doc_id = "doc-sem-bf-2"
        with sync_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{schema}".document_entities '
                     '(id, document_id, entity_type, entity_value, normalized_value, confidence) '
                     "VALUES (:id, :doc_id, 'YEARS_OF_EXP', '5+ years', '5+ years', 0.9)"),
                {"id": str(uuid.uuid4()), "doc_id": doc_id},
            )

        try:
            with sync_engine.begin() as conn:
                backfill_module.backfill_semantic_values_for_document(conn, schema, tid, doc_id)

            with sync_engine.begin() as conn:
                first_count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".document_entities WHERE document_id = :d'), {"d": doc_id}
                ).scalar()
                first_row = conn.execute(
                    text(f'SELECT value_number FROM "{schema}".document_entities WHERE document_id = :d'), {"d": doc_id}
                ).fetchone()

            with sync_engine.begin() as conn:
                backfill_module.backfill_semantic_values_for_document(conn, schema, tid, doc_id)

            with sync_engine.begin() as conn:
                second_count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}".document_entities WHERE document_id = :d'), {"d": doc_id}
                ).scalar()
                second_row = conn.execute(
                    text(f'SELECT value_number FROM "{schema}".document_entities WHERE document_id = :d'), {"d": doc_id}
                ).fetchone()

            assert first_count == second_count
            assert first_row.value_number == second_row.value_number
        finally:
            await self._teardown(engine, sync_engine, tid, schema)
            sync_engine.dispose()

    async def test_backfill_leaves_text_and_location_columns_untouched(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine
        from src.shared.config import settings

        tid = f"sem-bf-untouched-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema)

        doc_id = "doc-sem-bf-3"
        de_id = str(uuid.uuid4())
        with sync_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{schema}".document_entities '
                     "(id, document_id, entity_type, entity_value, normalized_value, confidence, page_number, char_start, char_end) "
                     "VALUES (:id, :doc_id, 'YEARS_OF_EXP', '5+ years', '5+ years', 0.9, 3, 10, 18)"),
                {"id": de_id, "doc_id": doc_id},
            )

        try:
            with sync_engine.begin() as conn:
                before = conn.execute(
                    text(f'SELECT entity_value, normalized_value, confidence, page_number, char_start, char_end '
                         f'FROM "{schema}".document_entities WHERE id = :id'),
                    {"id": de_id},
                ).fetchone()

            with sync_engine.begin() as conn:
                backfill_module.backfill_semantic_values_for_document(conn, schema, tid, doc_id)

            with sync_engine.begin() as conn:
                after = conn.execute(
                    text(f'SELECT entity_value, normalized_value, confidence, page_number, char_start, char_end '
                         f'FROM "{schema}".document_entities WHERE id = :id'),
                    {"id": de_id},
                ).fetchone()

            assert before._mapping == after._mapping
        finally:
            await self._teardown(engine, sync_engine, tid, schema)
            sync_engine.dispose()
