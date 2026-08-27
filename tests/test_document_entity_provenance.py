"""Covers verification.md rows 56-63.

`document_entities` could not previously answer "what did BERT originally extract?" at
all — one value per field, no history. The provenance columns answer that and "what
exactly did the post-processor change?", while staying NULL for the majority of rows
nothing touched, so a NULL *means* unchanged rather than unknown."""

import os
import uuid

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")

import pytest
from sqlalchemy import create_engine, text

from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.document_entity_store import insert_document_entities
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.shared.config import settings

SENTENCE = "Recruiter HANNAH studied JAVA at Centizen Inc. in Chennai"
TOKENS = SENTENCE.split()

_DOCUMENT_ENTITIES_DDL = """
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
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
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
        postprocess_at TIMESTAMPTZ,
        extraction_schema_version INTEGER NOT NULL DEFAULT 1,
        occurrence_count INTEGER NOT NULL DEFAULT 1
    )
"""


def _token_records(tokens=TOKENS, page_number=0):
    records = []
    offset = 0
    for token in tokens:
        records.append({
            "token": token,
            "page_number": page_number,
            "char_start": offset,
            "char_end": offset + len(token),
        })
        offset += len(token) + 1
    return records


def _entity(entity_type, value, word_start=0, word_end=None, confidence=0.2):
    records = _token_records()
    end = word_end if word_end is not None else word_start
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=canonicalize(value),
        confidence=confidence,
        page_number=0,
        char_start=records[word_start]["char_start"],
        char_end=records[end]["char_end"],
        word_index_start=word_start,
        word_index_end=end,
    )


@pytest.fixture(autouse=True)
def stable_settings(monkeypatch):
    monkeypatch.setattr(settings, "postprocess_confidence_threshold", 0.60)
    monkeypatch.setattr(settings, "postprocess_context_chars", 1200)
    monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4o-mini")
    monkeypatch.setattr(settings, "postprocess_prompt_version", "v1")


def _respond(monkeypatch, payload, tokens=100):
    monkeypatch.setattr(pp, "call_postprocessor", lambda s, u: (payload, tokens))


class TestOriginalValueSurvivesAModification:
    """Row 56 — the `COMPANY HANNAH` case."""

    def test_a_type_change_retains_the_original_type_and_value(self, monkeypatch):
        entities = [_entity("COMPANY", "HANNAH", word_start=1)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "NAME"}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"NAME", "COMPANY"})

        entity = outcome.entities[0]
        assert entity.entity_type == "NAME"
        assert entity.source_entity_type == "COMPANY"
        assert entity.entity_value == "HANNAH"

    def test_a_value_change_retains_the_original_value(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen", word_start=5)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        entity = outcome.entities[0]
        assert entity.entity_value == "Centizen Inc"
        assert entity.source_entity_value == "Centizen"
        assert entity.source_entity_type is None

    def test_a_change_of_both_retains_both(self, monkeypatch):
        entities = [_entity("DEGREE", "JAVA", word_start=3)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "JAVA", "entity_type": "PROGRAMMING_LANGUAGE"}
        ]})

        outcome, _ = pp.postprocess_document(
            entities, _token_records(), {}, {"PROGRAMMING_LANGUAGE", "DEGREE"}
        )

        entity = outcome.entities[0]
        assert entity.entity_type == "PROGRAMMING_LANGUAGE"
        assert entity.source_entity_type == "DEGREE"
        assert entity.source_entity_value is None, "the value did not actually change"


class TestUnchangedRowsDoNotDuplicate:
    """Row 57 — a NULL means unchanged, not unknown."""

    def test_a_keep_leaves_the_source_columns_null(self, monkeypatch):
        entities = [_entity("COMPANY", "Centizen Inc.", word_start=5, word_end=6)]
        _respond(monkeypatch, {"decisions": [{"candidate_id": 0, "decision": "keep"}]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        entity = outcome.entities[0]
        assert entity.postprocess_status == "kept"
        assert entity.source_entity_value is None
        assert entity.source_entity_type is None


class TestNeverPostprocessedRowsAreDistinguishable:
    """Row 58."""

    def test_a_bert_only_entity_carries_not_applied_and_null_provenance(self):
        entity = _entity("COMPANY", "Centizen Inc.", word_start=5, word_end=6, confidence=0.99)

        assert entity.postprocess_status == "not_applied"
        assert entity.source_entity_value is None
        assert entity.source_entity_type is None
        assert entity.postprocess_model is None
        assert entity.postprocess_prompt_version is None
        assert entity.postprocess_at is None


class TestModelAndPromptVersionAreRecorded:
    """Rows 59 and 60."""

    def test_a_modified_row_records_the_model_and_prompt_version(self, monkeypatch):
        monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4o-mini")
        monkeypatch.setattr(settings, "postprocess_prompt_version", "v1")
        entities = [_entity("COMPANY", "Centizen", word_start=5)]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."}
        ]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        entity = outcome.entities[0]
        assert entity.postprocess_model == "gpt-4o-mini"
        assert entity.postprocess_prompt_version == "v1"
        assert entity.postprocess_at is not None

    def test_the_recorded_model_is_the_one_actually_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4.1-mini")
        entities = [_entity("COMPANY", "Centizen", word_start=5)]
        _respond(monkeypatch, {"decisions": [{"candidate_id": 0, "decision": "keep"}]})

        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].postprocess_model == "gpt-4.1-mini"


@pytest.mark.asyncio
class TestProvenanceRoundTripsThroughTheDatabase:
    """Rows 59-62 at the storage boundary."""

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
            await conn.execute(text(_DOCUMENT_ENTITIES_DDL.format(schema=schema)))
        return schema

    async def _cleanup(self, engine, tid, schema):
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_all_provenance_columns_persist(self, monkeypatch, engine, setup_database):
        tid = f"prov-{uuid.uuid4().hex[:6]}"
        schema = await self._make_schema(engine, tid)
        sync_engine = create_engine(settings.database_url_sync)

        entities = [
            _entity("COMPANY", "HANNAH", word_start=1),
            _entity("COMPANY", "Centizen Inc.", word_start=5, word_end=6, confidence=0.99),
        ]
        _respond(monkeypatch, {"decisions": [
            {"candidate_id": 0, "decision": "modify", "entity_type": "NAME"}
        ]})
        outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"NAME", "COMPANY"})

        try:
            with sync_engine.begin() as conn:
                insert_document_entities(conn, schema, "doc-prov", outcome.entities)

            with sync_engine.begin() as conn:
                rows = conn.execute(text(f"""
                    SELECT entity_type, entity_value, source_entity_type, source_entity_value,
                           postprocess_status, postprocess_model, postprocess_prompt_version,
                           postprocess_at, extraction_schema_version, occurrence_count
                    FROM {schema}.document_entities ORDER BY entity_type
                """)).fetchall()

            changed = next(r for r in rows if r.entity_type == "NAME")
            assert changed.source_entity_type == "COMPANY"
            assert changed.postprocess_status == "modified"
            assert changed.postprocess_model == "gpt-4o-mini"
            assert changed.postprocess_prompt_version == "v1"
            assert changed.postprocess_at is not None

            untouched = next(r for r in rows if r.entity_type == "COMPANY")
            assert untouched.source_entity_type is None
            assert untouched.source_entity_value is None
            assert untouched.postprocess_status == "not_applied"
        finally:
            sync_engine.dispose()
            await self._cleanup(engine, tid, schema)

    async def test_rows_changed_by_a_prompt_version_are_queryable(self, monkeypatch, engine, setup_database):
        """Row 60 — a quality shift must be traceable to a prompt revision."""
        tid = f"prov-v-{uuid.uuid4().hex[:6]}"
        schema = await self._make_schema(engine, tid)
        sync_engine = create_engine(settings.database_url_sync)

        try:
            for version in ("v1", "v2"):
                monkeypatch.setattr(settings, "postprocess_prompt_version", version)
                entities = [_entity("COMPANY", "Centizen", word_start=5)]
                _respond(monkeypatch, {"decisions": [
                    {"candidate_id": 0, "decision": "modify", "value": "Centizen Inc."}
                ]})
                monkeypatch.setattr(pp, "PROMPT_VERSIONS", {version: pp.PROMPT_VERSIONS["v1"]})
                outcome, _ = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})
                with sync_engine.begin() as conn:
                    insert_document_entities(conn, schema, f"doc-{version}", outcome.entities)

            with sync_engine.begin() as conn:
                v1_count = conn.execute(text(
                    f"SELECT COUNT(*) FROM {schema}.document_entities WHERE postprocess_prompt_version = 'v1'"
                )).scalar()
                v2_count = conn.execute(text(
                    f"SELECT COUNT(*) FROM {schema}.document_entities WHERE postprocess_prompt_version = 'v2'"
                )).scalar()

            assert v1_count == 1
            assert v2_count == 1
        finally:
            sync_engine.dispose()
            await self._cleanup(engine, tid, schema)

    async def test_new_rows_carry_the_current_extraction_schema_version(self, engine, setup_database):
        """Row 61."""
        tid = f"prov-sv-{uuid.uuid4().hex[:6]}"
        schema = await self._make_schema(engine, tid)
        sync_engine = create_engine(settings.database_url_sync)

        try:
            with sync_engine.begin() as conn:
                insert_document_entities(conn, schema, "doc-sv", [_entity("COMPANY", "Centizen", word_start=5)])

            with sync_engine.begin() as conn:
                version = conn.execute(text(
                    f"SELECT extraction_schema_version FROM {schema}.document_entities"
                )).scalar()

            assert version == settings.extraction_schema_version
        finally:
            sync_engine.dispose()
            await self._cleanup(engine, tid, schema)

    async def test_pre_existing_rows_keep_their_uncalibrated_confidence(self, engine, setup_database):
        """Row 62 — a logit cannot be converted to a probability after the fact."""
        tid = f"prov-legacy-{uuid.uuid4().hex[:6]}"
        schema = await self._make_schema(engine, tid)
        sync_engine = create_engine(settings.database_url_sync)

        try:
            with sync_engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {schema}.document_entities
                        (id, document_id, entity_type, entity_value, normalized_value, confidence)
                    VALUES ('legacy-1', 'doc-legacy', 'COMPANY', 'Centizen INC', 'centizen inc', 5.6263)
                """))
                insert_document_entities(conn, schema, "doc-new", [_entity("COMPANY", "Centizen", word_start=5)])

            with sync_engine.begin() as conn:
                legacy = conn.execute(text(
                    f"SELECT confidence, extraction_schema_version FROM {schema}.document_entities WHERE id = 'legacy-1'"
                )).fetchone()
                fresh = conn.execute(text(
                    f"SELECT extraction_schema_version FROM {schema}.document_entities WHERE document_id = 'doc-new'"
                )).scalar()

            assert legacy.confidence == 5.6263
            assert legacy.extraction_schema_version == 1
            assert fresh == settings.extraction_schema_version
            assert fresh != legacy.extraction_schema_version
        finally:
            sync_engine.dispose()
            await self._cleanup(engine, tid, schema)


class TestConfidenceGatedSelectionIgnoresUncalibratedRows:
    """Row 63."""

    def test_an_uncalibrated_row_is_not_routed_by_confidence(self):
        entity = _entity("COMPANY", "Centizen Inc.", word_start=5, word_end=6, confidence=5.63)

        assert pp.select_candidates([entity], {}, extraction_schema_version=1) == []

    def test_a_calibrated_row_is_routed_by_confidence(self):
        entity = _entity("COMPANY", "Centizen Inc.", word_start=5, word_end=6, confidence=0.20)

        selected = pp.select_candidates(
            [entity], {}, extraction_schema_version=settings.extraction_schema_version
        )

        assert selected == [0]

    def test_the_default_schema_version_is_the_current_one(self):
        entity = _entity("COMPANY", "Centizen Inc.", word_start=5, word_end=6, confidence=0.20)

        assert pp.select_candidates([entity], {}) == [0]
