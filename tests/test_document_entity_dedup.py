"""Covers verification.md rows 64-67.

364 rows on the development tenant held only 289 distinct
`(document_id, entity_type, normalized_value)` triples: `node.js` appeared eight times
in one document, `react` six. `COUNT(*)` read that repetition as evidence weight."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")

import uuid

import pytest
from sqlalchemy import create_engine, text

from src.extraction_service.services.document_entity_store import insert_document_entities
from src.extraction_service.services.entity_normalizer import (
    NormalizedEntity,
    canonicalize,
    collapse_duplicates,
)
from src.shared.config import settings


def _entity(entity_type, value, page_number=0, char_start=0, char_end=None, confidence=0.9):
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=canonicalize(value),
        confidence=confidence,
        page_number=page_number,
        char_start=char_start,
        char_end=char_end if char_end is not None else char_start + len(value),
    )


class TestRepeatedMentionsCollapse:
    """Row 64."""

    def test_eight_mentions_become_one_row_with_a_count(self):
        entities = [_entity("TOOL_FRAMEWORK", "Node.js", char_start=100 * i) for i in range(8)]

        collapsed = collapse_duplicates(entities)

        assert len(collapsed) == 1
        assert collapsed[0].occurrence_count == 8

    def test_case_and_punctuation_variants_collapse_together(self):
        """They canonicalize to the same value, which is what the key uses."""
        entities = [
            _entity("COMPANY", "Centizen INC", char_start=10),
            _entity("COMPANY", "Centizen Inc.", char_start=200),
            _entity("COMPANY", "Centizen INC", char_start=400),
        ]

        collapsed = collapse_duplicates(entities)

        assert len(collapsed) == 1
        assert collapsed[0].occurrence_count == 3

    def test_a_single_mention_reports_a_count_of_one(self):
        collapsed = collapse_duplicates([_entity("COMPANY", "Polus Software")])

        assert collapsed[0].occurrence_count == 1

    def test_the_conservative_confidence_survives(self):
        entities = [
            _entity("TOOL_FRAMEWORK", "React", char_start=0, confidence=0.91),
            _entity("TOOL_FRAMEWORK", "React", char_start=50, confidence=0.44),
            _entity("TOOL_FRAMEWORK", "React", char_start=90, confidence=0.77),
        ]

        collapsed = collapse_duplicates(entities)

        assert collapsed[0].confidence == pytest.approx(0.44)


class TestFirstMentionSpanIsRetained:
    """Row 65 — citations point at this row, so its offsets must be real text."""

    def test_page_and_offsets_come_from_the_first_mention(self):
        entities = [
            _entity("TOOL_FRAMEWORK", "React", page_number=0, char_start=120),
            _entity("TOOL_FRAMEWORK", "React", page_number=2, char_start=4400),
        ]

        collapsed = collapse_duplicates(entities)

        assert collapsed[0].page_number == 0
        assert collapsed[0].char_start == 120
        assert collapsed[0].char_end == 125

    def test_document_order_decides_which_mention_is_first(self):
        entities = [
            _entity("COMPANY", "Zoho Technologies", page_number=1, char_start=900),
            _entity("COMPANY", "Zoho Technologies", page_number=0, char_start=10),
        ]

        collapsed = collapse_duplicates(entities)

        assert collapsed[0].page_number == 1
        assert collapsed[0].char_start == 900


class TestDistinctValuesAreNotCollapsed:
    """Row 66."""

    def test_values_canonicalizing_differently_keep_their_own_rows(self):
        entities = [
            _entity("COMPANY", "Centizen Inc."),
            _entity("COMPANY", "Wolfdale Software Solution"),
            _entity("COMPANY", "Manappuram Finance Ltd"),
        ]

        collapsed = collapse_duplicates(entities)

        assert len(collapsed) == 3
        assert all(e.occurrence_count == 1 for e in collapsed)

    def test_the_same_value_under_two_types_keeps_two_rows(self):
        entities = [
            _entity("COMPANY", "Hannah"),
            _entity("NAME", "Hannah"),
        ]

        collapsed = collapse_duplicates(entities)

        assert len(collapsed) == 2

    def test_input_order_is_preserved(self):
        entities = [
            _entity("PROGRAMMING_LANGUAGE", "Python"),
            _entity("PROGRAMMING_LANGUAGE", "Java"),
            _entity("PROGRAMMING_LANGUAGE", "Python"),
            _entity("PROGRAMMING_LANGUAGE", "JavaScript"),
        ]

        collapsed = collapse_duplicates(entities)

        assert [e.normalized_value for e in collapsed] == ["python", "java", "javascript"]

    def test_an_empty_input_returns_nothing(self):
        assert collapse_duplicates([]) == []


@pytest.mark.asyncio
class TestCollapsingDoesNotCrossDocuments:
    """Row 67 — the key is per document, so two documents naming the same skill keep
    one row each."""

    async def _make_schema(self, engine, tid):
        schema = f"tenant_{tid.replace('-', '_')}"
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await conn.execute(text(f"""
                CREATE TABLE {schema}.document_entities (
                    id VARCHAR PRIMARY KEY,
                    document_id VARCHAR NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    page_number INTEGER,
                    char_start INTEGER,
                    char_end INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    value_kind TEXT,
                    value_number DOUBLE PRECISION,
                    value_number_high DOUBLE PRECISION,
                    value_unit TEXT,
                    value_date DATE,
                    value_date_high DATE,
                    source_entity_value TEXT,
                    source_entity_type TEXT,
                    postprocess_status TEXT NOT NULL DEFAULT 'not_applied',
                    postprocess_model TEXT,
                    postprocess_prompt_version TEXT,
                    postprocess_at TIMESTAMP WITH TIME ZONE,
                    extraction_schema_version INTEGER NOT NULL DEFAULT 1,
                    occurrence_count INTEGER NOT NULL DEFAULT 1
                )
            """))
        return schema

    async def _cleanup(self, engine, tid, schema):
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_two_documents_keep_one_row_each(self, engine, setup_database):
        tid = f"dedup-{uuid.uuid4().hex[:6]}"
        schema = await self._make_schema(engine, tid)
        sync_engine = create_engine(settings.database_url_sync)

        try:
            doc_a_entities = collapse_duplicates([
                _entity("TOOL_FRAMEWORK", "React", char_start=0),
                _entity("TOOL_FRAMEWORK", "React", char_start=80),
            ])
            doc_b_entities = collapse_duplicates([
                _entity("TOOL_FRAMEWORK", "React", char_start=12),
            ])

            with sync_engine.begin() as conn:
                insert_document_entities(conn, schema, "doc-a", doc_a_entities)
                insert_document_entities(conn, schema, "doc-b", doc_b_entities)

            with sync_engine.begin() as conn:
                rows = conn.execute(text(f"""
                    SELECT document_id, occurrence_count
                    FROM {schema}.document_entities
                    WHERE entity_type = 'TOOL_FRAMEWORK' AND normalized_value = 'react'
                    ORDER BY document_id
                """)).fetchall()

            assert [(r.document_id, r.occurrence_count) for r in rows] == [("doc-a", 2), ("doc-b", 1)]
        finally:
            sync_engine.dispose()
            await self._cleanup(engine, tid, schema)

    async def test_occurrence_count_is_persisted(self, engine, setup_database):
        tid = f"dedup-c-{uuid.uuid4().hex[:6]}"
        schema = await self._make_schema(engine, tid)
        sync_engine = create_engine(settings.database_url_sync)

        try:
            entities = collapse_duplicates(
                [_entity("TOOL_FRAMEWORK", "Node.js", char_start=100 * i) for i in range(8)]
            )
            with sync_engine.begin() as conn:
                insert_document_entities(conn, schema, "doc-a", entities)

            with sync_engine.begin() as conn:
                row = conn.execute(text(f"""
                    SELECT occurrence_count, char_start, postprocess_status, extraction_schema_version
                    FROM {schema}.document_entities WHERE document_id = 'doc-a'
                """)).fetchone()
                total = conn.execute(text(
                    f"SELECT COUNT(*) FROM {schema}.document_entities WHERE document_id = 'doc-a'"
                )).scalar()

            assert total == 1
            assert row.occurrence_count == 8
            assert row.char_start == 0
            assert row.postprocess_status == "not_applied"
            assert row.extraction_schema_version == settings.extraction_schema_version
        finally:
            sync_engine.dispose()
            await self._cleanup(engine, tid, schema)
